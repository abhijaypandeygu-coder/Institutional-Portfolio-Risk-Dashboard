"""
M03.04.04 - Order Book Continuity and Resynchronization Engine.
Validates sequence monotonicity between snapshots and deltas, detects missing
packets / sequence gaps, isolates corrupt states, and dispatches resync requests to M02.
"""

from typing import Optional, Dict, Any, Tuple


class ContinuityValidator:
    """
    Evaluates sequence continuity and triggers resynchronization on gaps.
    """

    @staticmethod
    def evaluate(
        current_sequence: Optional[int],
        expected_sequence: Optional[int],
        is_snapshot: bool,
        max_allowed_gap: int = 0
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validates whether sequence progression is intact.
        Returns (is_continuous, error_reason, resync_payload).
        """
        if current_sequence is None:
            # If sequence tracking is not provided, cannot assert continuity break
            return True, None, None

        if is_snapshot:
            # Snapshots establish a new baseline sequence
            return True, None, None

        if expected_sequence is None:
            # First delta without expected sequence establishes baseline
            return True, None, None

        # Sequence gap evaluation
        if current_sequence == expected_sequence:
            return True, None, None

        if current_sequence < expected_sequence:
            # Out of order or duplicate delta
            reason = f"Duplicate or backwards delta sequence: current {current_sequence} < expected {expected_sequence}."
            resync_info = {
                "reason": "SEQUENCE_BACKWARDS",
                "from_sequence": current_sequence,
                "to_sequence": expected_sequence
            }
            return False, reason, resync_info

        # current_sequence > expected_sequence
        gap = current_sequence - expected_sequence
        if gap > max_allowed_gap:
            reason = f"Sequence gap detected: current {current_sequence} skipped past expected {expected_sequence} (gap: {gap} events)."
            resync_info = {
                "reason": "SEQUENCE_GAP",
                "from_sequence": expected_sequence,
                "to_sequence": current_sequence - 1
            }
            return False, reason, resync_info

        return True, None, None

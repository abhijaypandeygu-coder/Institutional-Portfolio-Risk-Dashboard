"""
Module 03.03: Timestamp Validation - Subfeature M03.03.02: Clock Drift Detector.
Evaluates:
- Apparent clock divergence (Local Receive Timestamp - Source Timestamp)
- True Clock Drift vs. Ordinary Network Transport Latency
- Multi-sample regression to compute Clock Drift Rate (ms/min)
- Clock uncertainty and synchronization health telemetry
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from backend.app.modules.market_data_quality.timestamp_validation.models import (
    ClockStatus,
    FinalTimestampStatus,
)


@dataclass
class ClockSample:
    source_timestamp: datetime
    local_receive_timestamp: datetime
    apparent_offset_ms: float
    estimated_latency_ms: float


@dataclass
class ClockEvaluationResult:
    status: ClockStatus
    final_status: FinalTimestampStatus
    apparent_offset_ms: float
    estimated_offset_ms: Optional[float]
    drift_rate_ms_per_min: Optional[float]
    uncertainty_ms: float
    reason: str


class ClockDriftDetector:
    """Estimates clock offset, detects divergence, and calculates drift rates over multi-sample windows."""

    def __init__(self, sample_window_size: int = 20):
        self.sample_window_size = sample_window_size
        # Key: (provider_id, feed_id) -> List[ClockSample]
        self._provider_samples: Dict[Tuple[str, str], List[ClockSample]] = {}

    def get_provider_key(self, provider_id: str, feed_id: str) -> Tuple[str, str]:
        return (provider_id.upper(), feed_id.upper())

    def evaluate(
        self,
        provider_id: str,
        feed_id: str,
        source_timestamp: datetime,
        local_receive_timestamp: datetime,
        estimated_network_latency_ms: float = 50.0,  # Baseline transport latency
        max_acceptable_offset_ms: float = 2000.0,     # Max acceptable apparent divergence (2s)
        max_drift_rate_ms_per_min: float = 100.0,    # Max acceptable drift rate (100ms/min)
    ) -> ClockEvaluationResult:
        """
        Calculates apparent offset = Receive Time - Source Time.
        Distinguishes network latency: Estimated Clock Offset = Apparent Offset - Estimated Transport Latency.
        Maintains sliding sample window to compute drift rate: d(Offset)/dt.
        """
        key = self.get_provider_key(provider_id, feed_id)
        
        # Apparent difference in milliseconds
        apparent_diff_ms = (local_receive_timestamp - source_timestamp).total_seconds() * 1000.0
        
        # Estimated true clock offset after accounting for transport latency
        estimated_offset_ms = apparent_diff_ms - estimated_network_latency_ms
        
        # Record sample
        if key not in self._provider_samples:
            self._provider_samples[key] = []
        
        samples = self._provider_samples[key]
        sample = ClockSample(
            source_timestamp=source_timestamp,
            local_receive_timestamp=local_receive_timestamp,
            apparent_offset_ms=apparent_diff_ms,
            estimated_latency_ms=estimated_network_latency_ms,
        )
        samples.append(sample)
        if len(samples) > self.sample_window_size:
            samples.pop(0)

        uncertainty_ms = estimated_network_latency_ms * 0.5  # 50% uncertainty bound on network jitter

        # Case 1: Apparent future-dating beyond uncertainty
        if apparent_diff_ms < -uncertainty_ms:
            # Source timestamp is significantly ahead of local receive timestamp!
            abs_future_ms = abs(apparent_diff_ms)
            if abs_future_ms > max_acceptable_offset_ms:
                return ClockEvaluationResult(
                    status=ClockStatus.SOURCE_CLOCK_OFFSET,
                    final_status=FinalTimestampStatus.QUARANTINED,
                    apparent_offset_ms=apparent_diff_ms,
                    estimated_offset_ms=estimated_offset_ms,
                    drift_rate_ms_per_min=None,
                    uncertainty_ms=uncertainty_ms,
                    reason=f"Source clock is {abs_future_ms:.1f}ms in the future relative to local clock.",
                )

        # Case 2: Excessive apparent divergence
        if apparent_diff_ms > max_acceptable_offset_ms:
            # High difference: could be severe clock lag or massive network delay
            return ClockEvaluationResult(
                status=ClockStatus.APPARENT_CLOCK_DIVERGENCE,
                final_status=FinalTimestampStatus.VALID_WITH_WARNING,
                apparent_offset_ms=apparent_diff_ms,
                estimated_offset_ms=estimated_offset_ms,
                drift_rate_ms_per_min=None,
                uncertainty_ms=uncertainty_ms,
                reason=f"Apparent time difference of {apparent_diff_ms:.1f}ms exceeds threshold {max_acceptable_offset_ms}ms.",
            )

        # Case 3: Drift Rate Calculation over Multi-Sample Window
        drift_rate: Optional[float] = None
        if len(samples) >= 5:
            first = samples[0]
            last = samples[-1]
            elapsed_sec = (last.local_receive_timestamp - first.local_receive_timestamp).total_seconds()
            if elapsed_sec > 5.0:  # At least 5 seconds between window edges
                offset_delta_ms = last.apparent_offset_ms - first.apparent_offset_ms
                drift_rate = (offset_delta_ms / (elapsed_sec / 60.0))  # ms per minute
                
                if abs(drift_rate) > max_drift_rate_ms_per_min:
                    return ClockEvaluationResult(
                        status=ClockStatus.CLOCK_DRIFT_DETECTED,
                        final_status=FinalTimestampStatus.VALID_WITH_WARNING,
                        apparent_offset_ms=apparent_diff_ms,
                        estimated_offset_ms=estimated_offset_ms,
                        drift_rate_ms_per_min=drift_rate,
                        uncertainty_ms=uncertainty_ms,
                        reason=f"Clock drift rate of {drift_rate:.1f} ms/min exceeds maximum {max_drift_rate_ms_per_min} ms/min.",
                    )

        return ClockEvaluationResult(
            status=ClockStatus.CLOCK_NORMAL,
            final_status=FinalTimestampStatus.VALID,
            apparent_offset_ms=apparent_diff_ms,
            estimated_offset_ms=estimated_offset_ms,
            drift_rate_ms_per_min=drift_rate,
            uncertainty_ms=uncertainty_ms,
            reason="Clock offset and transport delay within normal operational parameters.",
        )

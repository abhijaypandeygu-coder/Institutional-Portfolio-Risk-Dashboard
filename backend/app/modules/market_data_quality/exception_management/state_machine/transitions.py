"""
M03.08 Exception Management: State machine definitions, transitions, and validators.
Enforces strict separation between Workflow Status and Record Disposition.
"""
from enum import Enum
from typing import Set, Dict


class WorkflowStatus(str, Enum):
    OPEN = "OPEN"
    TRIAGED = "TRIAGED"
    IN_REVIEW = "IN_REVIEW"
    AWAITING_INFORMATION = "AWAITING_INFORMATION"
    CORRECTION_PENDING = "CORRECTION_PENDING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REPLAY_PENDING = "REPLAY_PENDING"
    REPLAYING = "REPLAYING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"
    REOPENED = "REOPENED"


class RecordDisposition(str, Enum):
    TRUSTED = "TRUSTED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    CORRECTION_PENDING = "CORRECTION_PENDING"
    READY_FOR_REPLAY = "READY_FOR_REPLAY"
    REPLAYING = "REPLAYING"
    REPLAYED = "REPLAYED"
    REPLAY_FAILED = "REPLAY_FAILED"
    RELEASE_PENDING = "RELEASE_PENDING"
    RELEASED = "RELEASED"


class ExceptionSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"
    UNKNOWN = "UNKNOWN"


class ExceptionPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Recoverability(str, Enum):
    RECOVERABLE = "RECOVERABLE"
    NON_RECOVERABLE = "NON_RECOVERABLE"
    UNDETERMINED = "UNDETERMINED"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class ReplayMode(str, Enum):
    SINGLE_RECORD = "SINGLE_RECORD"
    BATCH = "BATCH"
    TIME_WINDOW = "TIME_WINDOW"
    LATE_ARRIVAL = "LATE_ARRIVAL"
    CORRECTION_REPLAY = "CORRECTION_REPLAY"


class ReplayStatus(str, Enum):
    PENDING = "PENDING"
    REPLAYING = "REPLAYING"
    SUCCEEDED = "SUCCEEDED"
    SUCCEEDED_WITH_WARNINGS = "SUCCEEDED_WITH_WARNINGS"
    PARTIALLY_SUCCEEDED = "PARTIALLY_SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


# Valid transitions for Exception Workflow State Machine
WORKFLOW_TRANSITIONS: Dict[WorkflowStatus, Set[WorkflowStatus]] = {
    WorkflowStatus.OPEN: {WorkflowStatus.TRIAGED, WorkflowStatus.IN_REVIEW, WorkflowStatus.REPLAY_PENDING, WorkflowStatus.RESOLVED, WorkflowStatus.DISMISSED},
    WorkflowStatus.TRIAGED: {WorkflowStatus.IN_REVIEW, WorkflowStatus.AWAITING_INFORMATION, WorkflowStatus.CORRECTION_PENDING, WorkflowStatus.REPLAY_PENDING, WorkflowStatus.DISMISSED},
    WorkflowStatus.IN_REVIEW: {WorkflowStatus.AWAITING_INFORMATION, WorkflowStatus.CORRECTION_PENDING, WorkflowStatus.AWAITING_APPROVAL, WorkflowStatus.REPLAY_PENDING, WorkflowStatus.RESOLVED, WorkflowStatus.DISMISSED},
    WorkflowStatus.AWAITING_INFORMATION: {WorkflowStatus.IN_REVIEW, WorkflowStatus.CORRECTION_PENDING, WorkflowStatus.DISMISSED},
    WorkflowStatus.CORRECTION_PENDING: {WorkflowStatus.AWAITING_APPROVAL, WorkflowStatus.IN_REVIEW, WorkflowStatus.DISMISSED},
    WorkflowStatus.AWAITING_APPROVAL: {WorkflowStatus.APPROVED, WorkflowStatus.CORRECTION_PENDING, WorkflowStatus.IN_REVIEW},
    WorkflowStatus.APPROVED: {WorkflowStatus.REPLAY_PENDING, WorkflowStatus.RESOLVED},
    WorkflowStatus.REPLAY_PENDING: {WorkflowStatus.REPLAYING, WorkflowStatus.APPROVED, WorkflowStatus.IN_REVIEW},
    WorkflowStatus.REPLAYING: {WorkflowStatus.RESOLVED, WorkflowStatus.REPLAY_PENDING, WorkflowStatus.IN_REVIEW},
    WorkflowStatus.RESOLVED: {WorkflowStatus.REOPENED},
    WorkflowStatus.DISMISSED: {WorkflowStatus.REOPENED},
    WorkflowStatus.REOPENED: {WorkflowStatus.TRIAGED, WorkflowStatus.IN_REVIEW, WorkflowStatus.OPEN},
}


# Valid transitions for Observation Disposition State Machine
DISPOSITION_TRANSITIONS: Dict[RecordDisposition, Set[RecordDisposition]] = {
    RecordDisposition.TRUSTED: {RecordDisposition.QUARANTINED, RecordDisposition.REJECTED},
    RecordDisposition.QUARANTINED: {RecordDisposition.CORRECTION_PENDING, RecordDisposition.RELEASE_PENDING, RecordDisposition.REJECTED},
    RecordDisposition.REJECTED: {RecordDisposition.CORRECTION_PENDING},
    RecordDisposition.CORRECTION_PENDING: {RecordDisposition.READY_FOR_REPLAY, RecordDisposition.QUARANTINED, RecordDisposition.REJECTED},
    RecordDisposition.READY_FOR_REPLAY: {RecordDisposition.REPLAYING, RecordDisposition.CORRECTION_PENDING},
    RecordDisposition.REPLAYING: {RecordDisposition.REPLAYED, RecordDisposition.REPLAY_FAILED},
    RecordDisposition.REPLAYED: {RecordDisposition.RELEASE_PENDING, RecordDisposition.TRUSTED, RecordDisposition.QUARANTINED, RecordDisposition.REJECTED},
    RecordDisposition.REPLAY_FAILED: {RecordDisposition.CORRECTION_PENDING, RecordDisposition.READY_FOR_REPLAY, RecordDisposition.REJECTED},
    RecordDisposition.RELEASE_PENDING: {RecordDisposition.RELEASED, RecordDisposition.TRUSTED, RecordDisposition.QUARANTINED},
    RecordDisposition.RELEASED: {RecordDisposition.TRUSTED, RecordDisposition.QUARANTINED},
}


def validate_workflow_transition(current: WorkflowStatus, target: WorkflowStatus) -> bool:
    """Returns True if the transition from current to target is valid."""
    allowed = WORKFLOW_TRANSITIONS.get(current, set())
    return target in allowed


def validate_disposition_transition(current: RecordDisposition, target: RecordDisposition) -> bool:
    """Returns True if the disposition transition is valid."""
    allowed = DISPOSITION_TRANSITIONS.get(current, set())
    return target in allowed

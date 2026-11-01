"""State machine transitions and validators for Portfolio Lifecycle."""
from backend.app.modules.portfolio_management.portfolio_creation.models import PortfolioLifecycleStatus


# Permitted lifecycle state transitions
VALID_TRANSITIONS = {
    PortfolioLifecycleStatus.DRAFT: {
        PortfolioLifecycleStatus.PENDING_APPROVAL,
        PortfolioLifecycleStatus.REJECTED,
    },
    PortfolioLifecycleStatus.PENDING_APPROVAL: {
        PortfolioLifecycleStatus.APPROVED,
        PortfolioLifecycleStatus.REJECTED,
        PortfolioLifecycleStatus.DRAFT,
    },
    PortfolioLifecycleStatus.APPROVED: {
        PortfolioLifecycleStatus.ACTIVE,
        PortfolioLifecycleStatus.DRAFT,
    },
    PortfolioLifecycleStatus.ACTIVE: {
        PortfolioLifecycleStatus.SUSPENDED,
        PortfolioLifecycleStatus.CLOSING,
        PortfolioLifecycleStatus.CLOSED,
    },
    PortfolioLifecycleStatus.SUSPENDED: {
        PortfolioLifecycleStatus.ACTIVE,
        PortfolioLifecycleStatus.CLOSING,
        PortfolioLifecycleStatus.CLOSED,
    },
    PortfolioLifecycleStatus.CLOSING: {
        PortfolioLifecycleStatus.CLOSED,
        PortfolioLifecycleStatus.ACTIVE, # Re-open if closing aborted
    },
    PortfolioLifecycleStatus.CLOSED: {
        PortfolioLifecycleStatus.ARCHIVED,
    },
    PortfolioLifecycleStatus.ARCHIVED: set(),
    PortfolioLifecycleStatus.REJECTED: {
        PortfolioLifecycleStatus.DRAFT,
    },
}


def validate_lifecycle_transition(
    current_status: PortfolioLifecycleStatus,
    target_status: PortfolioLifecycleStatus
) -> bool:
    """Validates whether a lifecycle transition is allowed."""
    return target_status in VALID_TRANSITIONS.get(current_status, set())

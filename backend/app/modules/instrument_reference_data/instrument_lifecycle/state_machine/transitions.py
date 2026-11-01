import enum
from typing import Set, Dict


class ListingLifecycleStatus(str, enum.Enum):
    PENDING_LISTING = "PENDING_LISTING"
    LISTING_APPROVED = "LISTING_APPROVED"
    LISTED_NOT_YET_TRADING = "LISTED_NOT_YET_TRADING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    RESUMPTION_PENDING = "RESUMPTION_PENDING"
    DELISTING_ANNOUNCED = "DELISTING_ANNOUNCED"
    LAST_TRADING_DATE_REACHED = "LAST_TRADING_DATE_REACHED"
    DELISTED = "DELISTED"
    CANCELLED = "CANCELLED"
    INACTIVE = "INACTIVE"
    UNKNOWN = "UNKNOWN"


class InstrumentLifecycleStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    PENDING_ISSUANCE = "PENDING_ISSUANCE"
    ISSUED = "ISSUED"
    ACTIVE = "ACTIVE"
    PARTIALLY_TRADABLE = "PARTIALLY_TRADABLE"
    SUSPENDED_ALL_LISTINGS = "SUSPENDED_ALL_LISTINGS"
    RETIRED = "RETIRED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"


# Legal transitions for listing lifecycle
VALID_LISTING_TRANSITIONS: Dict[ListingLifecycleStatus, Set[ListingLifecycleStatus]] = {
    ListingLifecycleStatus.PENDING_LISTING: {
        ListingLifecycleStatus.LISTING_APPROVED,
        ListingLifecycleStatus.CANCELLED
    },
    ListingLifecycleStatus.LISTING_APPROVED: {
        ListingLifecycleStatus.LISTED_NOT_YET_TRADING,
        ListingLifecycleStatus.ACTIVE,
        ListingLifecycleStatus.CANCELLED
    },
    ListingLifecycleStatus.LISTED_NOT_YET_TRADING: {
        ListingLifecycleStatus.ACTIVE,
        ListingLifecycleStatus.CANCELLED
    },
    ListingLifecycleStatus.ACTIVE: {
        ListingLifecycleStatus.SUSPENDED,
        ListingLifecycleStatus.DELISTING_ANNOUNCED,
        ListingLifecycleStatus.DELISTED
    },
    ListingLifecycleStatus.SUSPENDED: {
        ListingLifecycleStatus.RESUMPTION_PENDING,
        ListingLifecycleStatus.ACTIVE,
        ListingLifecycleStatus.DELISTING_ANNOUNCED,
        ListingLifecycleStatus.DELISTED
    },
    ListingLifecycleStatus.RESUMPTION_PENDING: {
        ListingLifecycleStatus.ACTIVE,
        ListingLifecycleStatus.SUSPENDED
    },
    ListingLifecycleStatus.DELISTING_ANNOUNCED: {
        ListingLifecycleStatus.ACTIVE, # In case of cancelled/withdrawn delisting announcement
        ListingLifecycleStatus.SUSPENDED,
        ListingLifecycleStatus.LAST_TRADING_DATE_REACHED,
        ListingLifecycleStatus.DELISTED
    },
    ListingLifecycleStatus.LAST_TRADING_DATE_REACHED: {
        ListingLifecycleStatus.DELISTED
    },
    ListingLifecycleStatus.DELISTED: set(), # Terminal state unless explicit regulatory reinstatement
    ListingLifecycleStatus.CANCELLED: set() # Terminal state
}


def validate_listing_transition(current: ListingLifecycleStatus, target: ListingLifecycleStatus) -> bool:
    """
    Validates whether transitioning from current state to target state is legally permitted.
    """
    if current == target:
        return True
    allowed = VALID_LISTING_TRANSITIONS.get(current, set())
    return target in allowed

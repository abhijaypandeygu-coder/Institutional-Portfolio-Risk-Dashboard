"""
Pydantic contracts and validation schemas for M13.10 — Custom Views.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class ViewVisibility(str, Enum):
    PERSONAL = "PERSONAL"
    GROUP = "GROUP"


class ViewPermissionLevel(str, Enum):
    VIEW = "VIEW"
    EDIT = "EDIT"
    DUPLICATE = "DUPLICATE"
    MANAGE = "MANAGE"


class TimeRangeMode(str, Enum):
    RELATIVE = "RELATIVE"
    ABSOLUTE = "ABSOLUTE"


# -------------------------------------------------------------------------
# Layout & Widget Position Contracts
# -------------------------------------------------------------------------
class WidgetPosition(BaseModel):
    x: int = Field(..., ge=0, le=11, description="Grid column start index (0 to 11)")
    y: int = Field(..., ge=0, description="Grid row start index")
    width: int = Field(..., ge=1, le=12, description="Grid columns spanned (1 to 12)")
    height: int = Field(..., ge=1, le=24, description="Grid row height units")


class WidgetInstanceConfig(BaseModel):
    instance_id: str = Field(..., description="Unique client instance ID for this widget instance")
    widget_id: str = Field(..., description="Registered widget type from widget registry")
    widget_version: str = Field("1.0.0", description="Widget schema version")
    title_override: Optional[str] = Field(None, description="Optional custom title for the widget card")
    position: WidgetPosition
    is_visible: bool = Field(True, description="Whether widget is displayed in active layout")
    visualization_type: Optional[str] = Field(None, description="Chosen supported visualization format")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Widget specific configuration parameters")


class LayoutConfig(BaseModel):
    layout_version: str = Field("1.0.0", description="Layout engine schema version")
    grid_columns: int = Field(12, description="Number of columns in grid system")
    widgets: List[WidgetInstanceConfig] = Field(default_factory=list, description="Configured widget instances")


# -------------------------------------------------------------------------
# Filters and Time Range Contracts
# -------------------------------------------------------------------------
class FilterConfig(BaseModel):
    portfolio_ids: List[str] = Field(default_factory=list, description="Saved portfolio filter IDs")
    instrument_ids: List[str] = Field(default_factory=list, description="Saved instrument filter tickers or canonical IDs")
    sector_filters: List[str] = Field(default_factory=list, description="Saved sector/industry filter tags")
    selected_metrics: List[str] = Field(default_factory=list, description="Saved active metrics")
    custom_filters: Dict[str, Any] = Field(default_factory=dict, description="Widget-specific or custom filter parameters")


class TimeRangeConfig(BaseModel):
    mode: TimeRangeMode = Field(TimeRangeMode.RELATIVE, description="RELATIVE or ABSOLUTE time range")
    relative_preset: Optional[str] = Field("LAST_90_DAYS", description="E.g., TODAY, LAST_1_DAY, LAST_90_DAYS, YTD, 1Y")
    start_time: Optional[datetime] = Field(None, description="Explicit start timestamp if ABSOLUTE")
    end_time: Optional[datetime] = Field(None, description="Explicit end timestamp if ABSOLUTE")
    sampling_frequency: str = Field("DAILY", description="DAILY, WEEKLY, REALTIME")
    timezone: str = Field("UTC", description="Display timezone (e.g., UTC, Asia/Kolkata, America/New_York)")


# -------------------------------------------------------------------------
# View Requests & Responses
# -------------------------------------------------------------------------
class CustomViewCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="Name of custom view")
    description: Optional[str] = Field(None, max_length=1000)
    visibility: ViewVisibility = Field(ViewVisibility.PERSONAL)
    owner_group_id: Optional[str] = Field(None, description="Group ID if visibility is GROUP")
    layout_config: Optional[LayoutConfig] = None
    filter_config: Optional[FilterConfig] = None
    time_range_config: Optional[TimeRangeConfig] = None
    template_type: Optional[str] = Field(None, description="Optional starting template (e.g. 'PORTFOLIO_MONITORING')")


class CustomViewUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    visibility: Optional[ViewVisibility] = None
    owner_group_id: Optional[str] = None
    layout_config: Optional[LayoutConfig] = None
    filter_config: Optional[FilterConfig] = None
    time_range_config: Optional[TimeRangeConfig] = None
    is_archived: Optional[bool] = None
    expected_version: Optional[int] = Field(None, description="Optimistic concurrency control: expected version")


class CustomViewDuplicate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    visibility: ViewVisibility = Field(ViewVisibility.PERSONAL)


class ViewShareUpdate(BaseModel):
    principal_type: str = Field("GROUP", description="'USER' or 'GROUP'")
    principal_id: str = Field(..., description="User ID or Group ID")
    permission: ViewPermissionLevel = Field(ViewPermissionLevel.VIEW)


class ViewShareResponse(BaseModel):
    share_id: str
    view_id: str
    principal_type: str
    principal_id: str
    permission: ViewPermissionLevel
    granted_by_user_id: str
    created_at: datetime


class ViewVersionSummary(BaseModel):
    version_id: str
    view_id: str
    version_number: int
    changed_by_user_id: str
    change_summary: Optional[str] = None
    created_at: datetime


class CustomViewResponse(BaseModel):
    view_id: str
    owner_user_id: str
    name: str
    description: Optional[str] = None
    visibility: ViewVisibility
    owner_group_id: Optional[str] = None
    layout_config: LayoutConfig
    filter_config: FilterConfig
    time_range_config: TimeRangeConfig
    version: int
    is_archived: bool
    is_default: bool = False
    effective_permissions: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CustomViewListResponse(BaseModel):
    total_count: int
    views: List[CustomViewResponse]


class UserPreferenceUpdate(BaseModel):
    default_view_id: Optional[str] = None
    preferred_timezone: Optional[str] = None
    density_mode: Optional[str] = None
    auto_refresh_sec: Optional[int] = None
    theme_preference: Optional[str] = None


class UserPreferenceResponse(BaseModel):
    user_id: str
    default_view_id: Optional[str] = None
    preferred_timezone: str
    density_mode: str
    auto_refresh_sec: int
    theme_preference: str
    updated_at: datetime

"""
FastAPI router for M13.10 — Custom Views.

Provides institutional REST API endpoints for:
1. Widget Registry discovery & configuration schemas (`/widgets`, `/widgets/{widget_id}`)
2. Custom View CRUD, layout persistence & duplication (`/views`)
3. Layout version history and non-destructive restores (`/views/{view_id}/versions`)
4. Sharing controls and access permissions (`/views/{view_id}/sharing`)
5. User default view and dashboard density preferences (`/views/preferences`)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.dashboard_visualization.custom_views.schemas.custom_views_schemas import (
    CustomViewCreate,
    CustomViewUpdate,
    CustomViewDuplicate,
    CustomViewResponse,
    CustomViewListResponse,
    ViewShareUpdate,
    ViewShareResponse,
    ViewVersionSummary,
    UserPreferenceUpdate,
    UserPreferenceResponse,
)
from backend.app.modules.dashboard_visualization.custom_views.services.custom_views_service import (
    CustomViewsService,
)
from backend.app.modules.dashboard_visualization.custom_views.widget_registry import (
    WidgetRegistryService,
    WidgetDefinition,
)

router = APIRouter(prefix="/custom-views", tags=["M13.10 - Custom Views"])


# -----------------------------------------------------------------------------
# 1. Widget Registry Endpoints
# -----------------------------------------------------------------------------
@router.get(
    "/widgets",
    response_model=List[WidgetDefinition],
    summary="List all registered dashboard widgets from M13.01–M13.09",
)
async def list_registered_widgets():
    """
    Returns the central catalogue of institutional dashboard widgets available for custom layouts.
    """
    return WidgetRegistryService.get_all_widgets()


@router.get(
    "/widgets/{widget_id}",
    response_model=WidgetDefinition,
    summary="Get widget metadata, default configuration and dimension limits",
)
async def get_widget_definition(
    widget_id: str = Path(..., description="Registered widget identifier"),
):
    widget = WidgetRegistryService.get_widget(widget_id)
    if not widget:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Widget '{widget_id}' not found in registry.",
        )
    return widget


# -----------------------------------------------------------------------------
# 2. Custom View CRUD
# -----------------------------------------------------------------------------
@router.post(
    "/views",
    response_model=CustomViewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom dashboard view with layout and filters",
)
async def create_custom_view(
    req: CustomViewCreate,
    user_id: str = Query("DEFAULT_USER", description="Authenticated user ID"),
    user_groups: Optional[List[str]] = Query(None, description="Groups the user belongs to"),
    db: AsyncSession = Depends(get_db),
):
    service = CustomViewsService(db)
    return await service.create_custom_view(user_id=user_id, req=req, user_groups=user_groups)


@router.get(
    "/views",
    response_model=CustomViewListResponse,
    summary="List all accessible custom views (owned or shared)",
)
async def list_custom_views(
    visibility: Optional[str] = Query(None, description="Filter by 'PERSONAL' or 'GROUP'"),
    search: Optional[str] = Query(None, description="Search view by name"),
    user_id: str = Query("DEFAULT_USER", description="Authenticated user ID"),
    user_groups: Optional[List[str]] = Query(None, description="Groups the user belongs to"),
    db: AsyncSession = Depends(get_db),
):
    service = CustomViewsService(db)
    return await service.list_custom_views(
        user_id=user_id, user_groups=user_groups, visibility=visibility, search=search
    )


@router.get(
    "/views/{view_id}",
    response_model=CustomViewResponse,
    summary="Retrieve a specific custom view configuration",
)
async def get_custom_view(
    view_id: str = Path(..., description="Custom view ID"),
    user_id: str = Query("DEFAULT_USER", description="Authenticated user ID"),
    user_groups: Optional[List[str]] = Query(None, description="Groups the user belongs to"),
    db: AsyncSession = Depends(get_db),
):
    service = CustomViewsService(db)
    return await service.get_custom_view(view_id=view_id, user_id=user_id, user_groups=user_groups)


@router.patch(
    "/views/{view_id}",
    response_model=CustomViewResponse,
    summary="Update layout, filters, or widget configurations (with version conflict check)",
)
async def update_custom_view(
    req: CustomViewUpdate,
    view_id: str = Path(..., description="Custom view ID"),
    user_id: str = Query("DEFAULT_USER", description="Authenticated user ID"),
    user_groups: Optional[List[str]] = Query(None, description="Groups the user belongs to"),
    db: AsyncSession = Depends(get_db),
):
    service = CustomViewsService(db)
    return await service.update_custom_view(
        view_id=view_id, user_id=user_id, req=req, user_groups=user_groups
    )


@router.post(
    "/views/{view_id}/duplicate",
    response_model=CustomViewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate an existing view into a personal workspace",
)
async def duplicate_custom_view(
    req: CustomViewDuplicate,
    view_id: str = Path(..., description="Source view ID"),
    user_id: str = Query("DEFAULT_USER", description="Authenticated user ID"),
    user_groups: Optional[List[str]] = Query(None, description="Groups the user belongs to"),
    db: AsyncSession = Depends(get_db),
):
    service = CustomViewsService(db)
    return await service.duplicate_custom_view(
        view_id=view_id, user_id=user_id, req=req, user_groups=user_groups
    )


@router.delete(
    "/views/{view_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive/Delete a custom view",
)
async def delete_custom_view(
    view_id: str = Path(..., description="Custom view ID"),
    user_id: str = Query("DEFAULT_USER", description="Authenticated user ID"),
    user_groups: Optional[List[str]] = Query(None, description="Groups the user belongs to"),
    db: AsyncSession = Depends(get_db),
):
    service = CustomViewsService(db)
    await service.delete_custom_view(view_id=view_id, user_id=user_id, user_groups=user_groups)
    return None


# -----------------------------------------------------------------------------
# 3. Sharing Controls
# -----------------------------------------------------------------------------
@router.put(
    "/views/{view_id}/sharing",
    response_model=List[ViewShareResponse],
    summary="Update group or user sharing permissions for a view",
)
async def update_view_sharing(
    shares: List[ViewShareUpdate],
    view_id: str = Path(..., description="Custom view ID"),
    user_id: str = Query("DEFAULT_USER", description="Authenticated user ID"),
    user_groups: Optional[List[str]] = Query(None, description="Groups the user belongs to"),
    db: AsyncSession = Depends(get_db),
):
    service = CustomViewsService(db)
    return await service.update_view_sharing(
        view_id=view_id, user_id=user_id, shares=shares, user_groups=user_groups
    )


# -----------------------------------------------------------------------------
# 4. Version History & Restore
# -----------------------------------------------------------------------------
@router.get(
    "/views/{view_id}/versions",
    response_model=List[ViewVersionSummary],
    summary="List immutable version snapshots of a custom view",
)
async def list_view_versions(
    view_id: str = Path(..., description="Custom view ID"),
    user_id: str = Query("DEFAULT_USER", description="Authenticated user ID"),
    user_groups: Optional[List[str]] = Query(None, description="Groups the user belongs to"),
    db: AsyncSession = Depends(get_db),
):
    service = CustomViewsService(db)
    return await service.list_view_versions(view_id=view_id, user_id=user_id, user_groups=user_groups)


@router.post(
    "/views/{view_id}/versions/{version_number}/restore",
    response_model=CustomViewResponse,
    summary="Restore a previous layout version (creates a new sequential version)",
)
async def restore_view_version(
    view_id: str = Path(..., description="Custom view ID"),
    version_number: int = Path(..., description="Version number to restore"),
    user_id: str = Query("DEFAULT_USER", description="Authenticated user ID"),
    user_groups: Optional[List[str]] = Query(None, description="Groups the user belongs to"),
    db: AsyncSession = Depends(get_db),
):
    service = CustomViewsService(db)
    return await service.restore_view_version(
        view_id=view_id, version_number=version_number, user_id=user_id, user_groups=user_groups
    )


# -----------------------------------------------------------------------------
# 5. User Preferences
# -----------------------------------------------------------------------------
@router.get(
    "/preferences",
    response_model=UserPreferenceResponse,
    summary="Get user view preferences (default view, density, timezone)",
)
async def get_user_preferences(
    user_id: str = Query("DEFAULT_USER", description="Authenticated user ID"),
    db: AsyncSession = Depends(get_db),
):
    service = CustomViewsService(db)
    return await service.get_or_create_user_preferences(user_id=user_id)


@router.put(
    "/preferences",
    response_model=UserPreferenceResponse,
    summary="Update user view preferences",
)
async def update_user_preferences(
    req: UserPreferenceUpdate,
    user_id: str = Query("DEFAULT_USER", description="Authenticated user ID"),
    db: AsyncSession = Depends(get_db),
):
    service = CustomViewsService(db)
    return await service.update_user_preferences(user_id=user_id, req=req)

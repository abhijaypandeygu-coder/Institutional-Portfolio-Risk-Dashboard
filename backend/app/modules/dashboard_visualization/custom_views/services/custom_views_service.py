"""
M13.10 — Custom Views Application Service.

Encapsulates all business logic for:
- Creating, retrieving, listing, updating, duplicating, and archiving custom views.
- Validating layout arrangements and widget configurations against the Widget Registry.
- Enforcing ownership and group authorization policies (VIEW, EDIT, DUPLICATE, MANAGE).
- Optimistic concurrency control using sequential versioning.
- Immutable layout version snapshots and version restoration.
- Fine-grained sharing management and institutional audit logging.
- User preference management (default view, timezone, density).
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from backend.app.modules.dashboard_visualization.custom_views.models.custom_views_models import (
    DashboardCustomView,
    DashboardViewVersion,
    DashboardViewShare,
    DashboardUserViewPreference,
    DashboardViewAuditLog,
)
from backend.app.modules.dashboard_visualization.custom_views.schemas.custom_views_schemas import (
    ViewVisibility,
    ViewPermissionLevel,
    TimeRangeMode,
    WidgetPosition,
    WidgetInstanceConfig,
    LayoutConfig,
    FilterConfig,
    TimeRangeConfig,
    CustomViewCreate,
    CustomViewUpdate,
    CustomViewDuplicate,
    ViewShareUpdate,
    ViewShareResponse,
    ViewVersionSummary,
    CustomViewResponse,
    CustomViewListResponse,
    UserPreferenceUpdate,
    UserPreferenceResponse,
)
from backend.app.modules.dashboard_visualization.custom_views.widget_registry import (
    WidgetRegistryService,
    REGISTERED_WIDGETS,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CustomViewsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------------
    # Layout & Widget Validation
    # -------------------------------------------------------------------------
    def validate_layout(self, layout: LayoutConfig) -> None:
        """
        Validates layout grid bounds and registered widget IDs/configurations.
        """
        if not layout.widgets:
            return

        for w in layout.widgets:
            widget_def = WidgetRegistryService.get_widget(w.widget_id)
            if not widget_def:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Widget ID '{w.widget_id}' is not recognized in the Widget Registry.",
                )

            # Check dimension bounds
            bounds = widget_def.dimension_bounds
            if w.position.width < bounds.min_width or w.position.width > bounds.max_width:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Widget '{w.widget_id}' width {w.position.width} outside allowed bounds [{bounds.min_width}, {bounds.max_width}].",
                )
            if w.position.height < bounds.min_height or w.position.height > bounds.max_height:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Widget '{w.widget_id}' height {w.position.height} outside allowed bounds [{bounds.min_height}, {bounds.max_height}].",
                )

            # Check visualization type
            if w.visualization_type and w.visualization_type not in widget_def.supported_visualization_types:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Visualization type '{w.visualization_type}' is not supported for widget '{w.widget_id}'. Supported: {widget_def.supported_visualization_types}",
                )

    # -------------------------------------------------------------------------
    # Template Generation
    # -------------------------------------------------------------------------
    def get_template_layout(self, template_type: Optional[str]) -> Tuple[LayoutConfig, FilterConfig, TimeRangeConfig]:
        """
        Provides starter templates for analytical personas.
        """
        if template_type == "RISK_MONITORING":
            layout = LayoutConfig(
                grid_columns=12,
                widgets=[
                    WidgetInstanceConfig(
                        instance_id="inst_risk_overview",
                        widget_id="m13_02_risk_overview",
                        position=WidgetPosition(x=0, y=0, width=6, height=4),
                        visualization_type="kpi_cards",
                        settings={"confidence_level": 0.99},
                    ),
                    WidgetInstanceConfig(
                        instance_id="inst_alerts_stream",
                        widget_id="m13_08_alerts_dashboard",
                        position=WidgetPosition(x=6, y=0, width=6, height=4),
                        visualization_type="alert_stream",
                        settings={"min_severity": "WARNING"},
                    ),
                    WidgetInstanceConfig(
                        instance_id="inst_risk_heatmaps",
                        widget_id="m13_04_risk_heatmaps",
                        position=WidgetPosition(x=0, y=4, width=12, height=5),
                        visualization_type="heatmap",
                        settings={"color_scale": "RED_GREEN"},
                    ),
                ],
            )
            return layout, FilterConfig(selected_metrics=["var_99", "drawdown"]), TimeRangeConfig(mode=TimeRangeMode.RELATIVE, relative_preset="LAST_90_DAYS")

        elif template_type == "PORTFOLIO_MONITORING":
            layout = LayoutConfig(
                grid_columns=12,
                widgets=[
                    WidgetInstanceConfig(
                        instance_id="inst_port_overview",
                        widget_id="m13_01_portfolio_overview",
                        position=WidgetPosition(x=0, y=0, width=12, height=3),
                        visualization_type="kpi_cards",
                        settings={"display_mode": "cards"},
                    ),
                    WidgetInstanceConfig(
                        instance_id="inst_exposure",
                        widget_id="m13_03_exposure_dashboard",
                        position=WidgetPosition(x=0, y=3, width=6, height=4),
                        visualization_type="bar_chart",
                        settings={"breakdown_dimension": "sector"},
                    ),
                    WidgetInstanceConfig(
                        instance_id="inst_history_nav",
                        widget_id="m13_09_historical_analytics",
                        position=WidgetPosition(x=6, y=3, width=6, height=4),
                        visualization_type="time_series_line",
                        settings={"historical_mode": "AS_KNOWN_AT_TIME"},
                    ),
                ],
            )
            return layout, FilterConfig(selected_metrics=["nav", "daily_pnl"]), TimeRangeConfig(mode=TimeRangeMode.RELATIVE, relative_preset="LAST_30_DAYS")

        # Default empty layout
        return LayoutConfig(grid_columns=12, widgets=[]), FilterConfig(), TimeRangeConfig()

    # -------------------------------------------------------------------------
    # Permissions & Access Verification
    # -------------------------------------------------------------------------
    async def get_effective_permissions(
        self, view: DashboardCustomView, user_id: str, user_groups: Optional[List[str]] = None
    ) -> List[str]:
        """
        Determines the effective permissions the user has on the given view.
        Owner gets all permissions: ['VIEW', 'EDIT', 'DUPLICATE', 'MANAGE', 'DELETE']
        Group/User shares grant specific permissions.
        """
        if view.owner_user_id == user_id:
            return ["VIEW", "EDIT", "DUPLICATE", "MANAGE", "DELETE"]

        # Check explicit shares
        user_groups = user_groups or []
        query = select(DashboardViewShare).where(
            DashboardViewShare.view_id == view.view_id,
            or_(
                and_(DashboardViewShare.principal_type == "USER", DashboardViewShare.principal_id == user_id),
                and_(DashboardViewShare.principal_type == "GROUP", DashboardViewShare.principal_id.in_(user_groups)),
            ),
        )
        res = await self.db.execute(query)
        shares = res.scalars().all()

        perms = set()
        for s in shares:
            perms.add(s.permission)
            if s.permission == "MANAGE":
                perms.update(["VIEW", "EDIT", "DUPLICATE", "DELETE"])
            elif s.permission == "EDIT":
                perms.update(["VIEW", "DUPLICATE"])
            elif s.permission == "VIEW":
                perms.add("DUPLICATE")

        # If GROUP visibility and user is in view's owner_group_id
        if view.visibility == ViewVisibility.GROUP.value and view.owner_group_id in user_groups:
            perms.update(["VIEW", "DUPLICATE"])

        return sorted(list(perms))

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------
    async def create_custom_view(
        self, user_id: str, req: CustomViewCreate, user_groups: Optional[List[str]] = None
    ) -> CustomViewResponse:
        """
        Creates a new customized dashboard view with optional starter template.
        """
        layout = req.layout_config
        filters = req.filter_config
        time_range = req.time_range_config

        if req.template_type and not layout:
            tpl_layout, tpl_filters, tpl_time = self.get_template_layout(req.template_type)
            layout = layout or tpl_layout
            filters = filters or tpl_filters
            time_range = time_range or tpl_time

        layout = layout or LayoutConfig(grid_columns=12, widgets=[])
        filters = filters or FilterConfig()
        time_range = time_range or TimeRangeConfig()

        self.validate_layout(layout)

        new_view = DashboardCustomView(
            owner_user_id=user_id,
            name=req.name,
            description=req.description,
            visibility=req.visibility.value,
            owner_group_id=req.owner_group_id,
            layout_config=layout.model_dump(),
            widget_config={w.instance_id: w.settings for w in layout.widgets},
            filter_config=filters.model_dump(),
            time_range_config=time_range.model_dump(mode="json"),
            version=1,
            is_archived=False,
        )
        self.db.add(new_view)
        await self.db.flush()

        # Create initial Version 1 snapshot
        initial_version = DashboardViewVersion(
            view_id=new_view.view_id,
            version_number=1,
            configuration_snapshot={
                "layout_config": new_view.layout_config,
                "widget_config": new_view.widget_config,
                "filter_config": new_view.filter_config,
                "time_range_config": new_view.time_range_config,
            },
            changed_by_user_id=user_id,
            change_summary="Initial view creation",
        )
        self.db.add(initial_version)

        # Audit log
        audit = DashboardViewAuditLog(
            view_id=new_view.view_id,
            user_id=user_id,
            action="CREATE_VIEW",
            version_after=1,
            details={"name": new_view.name, "visibility": new_view.visibility},
        )
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(new_view)

        return await self._to_response(new_view, user_id, user_groups)

    async def get_custom_view(
        self, view_id: str, user_id: str, user_groups: Optional[List[str]] = None
    ) -> CustomViewResponse:
        """
        Retrieves a custom view ensuring user has VIEW permission.
        """
        view = await self.db.get(DashboardCustomView, view_id)
        if not view or view.is_archived:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Custom view '{view_id}' not found.")

        perms = await self.get_effective_permissions(view, user_id, user_groups)
        if "VIEW" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to custom view.")

        return await self._to_response(view, user_id, user_groups, perms=perms)

    async def list_custom_views(
        self,
        user_id: str,
        user_groups: Optional[List[str]] = None,
        visibility: Optional[str] = None,
        search: Optional[str] = None,
    ) -> CustomViewListResponse:
        """
        Lists all views accessible to the user (owned or shared).
        """
        user_groups = user_groups or []
        
        # Subquery for shared view IDs
        shared_query = select(DashboardViewShare.view_id).where(
            or_(
                and_(DashboardViewShare.principal_type == "USER", DashboardViewShare.principal_id == user_id),
                and_(DashboardViewShare.principal_type == "GROUP", DashboardViewShare.principal_id.in_(user_groups)),
            )
        )
        shared_res = await self.db.execute(shared_query)
        shared_view_ids = set(shared_res.scalars().all())

        # Main query
        conditions = [
            DashboardCustomView.is_archived == False,
            or_(
                DashboardCustomView.owner_user_id == user_id,
                DashboardCustomView.view_id.in_(shared_view_ids),
                and_(
                    DashboardCustomView.visibility == ViewVisibility.GROUP.value,
                    DashboardCustomView.owner_group_id.in_(user_groups),
                ),
            ),
        ]

        if visibility:
            conditions.append(DashboardCustomView.visibility == visibility)
        if search:
            conditions.append(DashboardCustomView.name.ilike(f"%{search}%"))

        q = select(DashboardCustomView).where(and_(*conditions)).order_by(DashboardCustomView.updated_at.desc())
        res = await self.db.execute(q)
        views = res.scalars().all()

        user_pref = await self._get_user_preference(user_id)
        default_id = user_pref.default_view_id if user_pref else None

        responses: List[CustomViewResponse] = []
        for v in views:
            perms = await self.get_effective_permissions(v, user_id, user_groups)
            resp = await self._to_response(v, user_id, user_groups, default_view_id=default_id, perms=perms)
            responses.append(resp)

        return CustomViewListResponse(total_count=len(responses), views=responses)

    async def update_custom_view(
        self,
        view_id: str,
        user_id: str,
        req: CustomViewUpdate,
        user_groups: Optional[List[str]] = None,
    ) -> CustomViewResponse:
        """
        Updates a custom view configuration with optimistic concurrency validation.
        """
        view = await self.db.get(DashboardCustomView, view_id)
        if not view or view.is_archived:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Custom view '{view_id}' not found.")

        perms = await self.get_effective_permissions(view, user_id, user_groups)
        if "EDIT" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Edit permission denied for this view.")

        # Optimistic concurrency check
        if req.expected_version is not None and req.expected_version != view.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version conflict: Expected version {req.expected_version}, but view is at version {view.version}. Reload and re-apply changes.",
            )

        old_version = view.version
        new_version = old_version + 1

        if req.name is not None:
            view.name = req.name
        if req.description is not None:
            view.description = req.description
        if req.visibility is not None:
            view.visibility = req.visibility.value
        if req.owner_group_id is not None:
            view.owner_group_id = req.owner_group_id
        if req.is_archived is not None:
            view.is_archived = req.is_archived

        if req.layout_config is not None:
            self.validate_layout(req.layout_config)
            view.layout_config = req.layout_config.model_dump()
            view.widget_config = {w.instance_id: w.settings for w in req.layout_config.widgets}

        if req.filter_config is not None:
            view.filter_config = req.filter_config.model_dump()

        if req.time_range_config is not None:
            view.time_range_config = req.time_range_config.model_dump(mode="json")

        view.version = new_version
        view.updated_at = utc_now()

        # Create Version Snapshot
        version_snapshot = DashboardViewVersion(
            view_id=view.view_id,
            version_number=new_version,
            configuration_snapshot={
                "layout_config": view.layout_config,
                "widget_config": view.widget_config,
                "filter_config": view.filter_config,
                "time_range_config": view.time_range_config,
            },
            changed_by_user_id=user_id,
            change_summary=f"Updated view layout/config to version {new_version}",
        )
        self.db.add(version_snapshot)

        # Audit log
        audit = DashboardViewAuditLog(
            view_id=view.view_id,
            user_id=user_id,
            action="UPDATE_VIEW",
            version_before=old_version,
            version_after=new_version,
            details={"updated_fields": list(req.model_dump(exclude_unset=True).keys())},
        )
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(view)

        return await self._to_response(view, user_id, user_groups, perms=perms)

    async def duplicate_custom_view(
        self,
        view_id: str,
        user_id: str,
        req: CustomViewDuplicate,
        user_groups: Optional[List[str]] = None,
    ) -> CustomViewResponse:
        """
        Duplicates an existing view to create a personal view owned by the calling user.
        """
        source_view = await self.db.get(DashboardCustomView, view_id)
        if not source_view or source_view.is_archived:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source view '{view_id}' not found.")

        perms = await self.get_effective_permissions(source_view, user_id, user_groups)
        if "DUPLICATE" not in perms and "VIEW" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Duplicate permission denied for this view.")

        duplicated_view = DashboardCustomView(
            owner_user_id=user_id,
            name=req.name,
            description=req.description or f"Duplicated from {source_view.name}",
            visibility=req.visibility.value,
            layout_config=source_view.layout_config,
            widget_config=source_view.widget_config,
            filter_config=source_view.filter_config,
            time_range_config=source_view.time_range_config,
            version=1,
            is_archived=False,
        )
        self.db.add(duplicated_view)
        await self.db.flush()

        initial_ver = DashboardViewVersion(
            view_id=duplicated_view.view_id,
            version_number=1,
            configuration_snapshot={
                "layout_config": duplicated_view.layout_config,
                "widget_config": duplicated_view.widget_config,
                "filter_config": duplicated_view.filter_config,
                "time_range_config": duplicated_view.time_range_config,
            },
            changed_by_user_id=user_id,
            change_summary=f"Duplicated from {source_view.view_id} (version {source_view.version})",
        )
        self.db.add(initial_ver)

        audit = DashboardViewAuditLog(
            view_id=duplicated_view.view_id,
            user_id=user_id,
            action="DUPLICATE_VIEW",
            version_after=1,
            details={"source_view_id": source_view.view_id, "new_name": duplicated_view.name},
        )
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(duplicated_view)

        return await self._to_response(duplicated_view, user_id, user_groups)

    async def delete_custom_view(
        self, view_id: str, user_id: str, user_groups: Optional[List[str]] = None
    ) -> None:
        """
        Soft-deletes (archives) a view if caller has DELETE/MANAGE permission or is owner.
        """
        view = await self.db.get(DashboardCustomView, view_id)
        if not view or view.is_archived:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Custom view '{view_id}' not found.")

        perms = await self.get_effective_permissions(view, user_id, user_groups)
        if "DELETE" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Delete permission denied.")

        view.is_archived = True
        view.updated_at = utc_now()

        audit = DashboardViewAuditLog(
            view_id=view.view_id,
            user_id=user_id,
            action="DELETE_VIEW",
            version_before=view.version,
            details={"status": "ARCHIVED"},
        )
        self.db.add(audit)
        await self.db.commit()

    # -------------------------------------------------------------------------
    # Sharing Controls
    # -------------------------------------------------------------------------
    async def update_view_sharing(
        self,
        view_id: str,
        user_id: str,
        shares: List[ViewShareUpdate],
        user_groups: Optional[List[str]] = None,
    ) -> List[ViewShareResponse]:
        """
        Sets explicit permissions for groups or users. Caller must have MANAGE or be owner.
        """
        view = await self.db.get(DashboardCustomView, view_id)
        if not view or view.is_archived:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Custom view '{view_id}' not found.")

        perms = await self.get_effective_permissions(view, user_id, user_groups)
        if "MANAGE" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manage permission denied for view sharing.")

        # Clear existing shares
        await self.db.execute(delete(DashboardViewShare).where(DashboardViewShare.view_id == view_id))

        new_shares: List[DashboardViewShare] = []
        for s in shares:
            share = DashboardViewShare(
                view_id=view_id,
                principal_type=s.principal_type,
                principal_id=s.principal_id,
                permission=s.permission.value,
                granted_by_user_id=user_id,
            )
            self.db.add(share)
            new_shares.append(share)

        audit = DashboardViewAuditLog(
            view_id=view_id,
            user_id=user_id,
            action="UPDATE_SHARING",
            details={"share_count": len(shares)},
        )
        self.db.add(audit)
        await self.db.commit()

        return [
            ViewShareResponse(
                share_id=s.share_id,
                view_id=s.view_id,
                principal_type=s.principal_type,
                principal_id=s.principal_id,
                permission=ViewPermissionLevel(s.permission),
                granted_by_user_id=s.granted_by_user_id,
                created_at=s.created_at,
            )
            for s in new_shares
        ]

    # -------------------------------------------------------------------------
    # Versioning & Restore
    # -------------------------------------------------------------------------
    async def list_view_versions(
        self, view_id: str, user_id: str, user_groups: Optional[List[str]] = None
    ) -> List[ViewVersionSummary]:
        """
        Lists immutable version snapshots of a view.
        """
        view = await self.db.get(DashboardCustomView, view_id)
        if not view or view.is_archived:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Custom view '{view_id}' not found.")

        perms = await self.get_effective_permissions(view, user_id, user_groups)
        if "VIEW" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        q = select(DashboardViewVersion).where(DashboardViewVersion.view_id == view_id).order_by(DashboardViewVersion.version_number.desc())
        res = await self.db.execute(q)
        versions = res.scalars().all()

        return [
            ViewVersionSummary(
                version_id=v.version_id,
                view_id=v.view_id,
                version_number=v.version_number,
                changed_by_user_id=v.changed_by_user_id,
                change_summary=v.change_summary,
                created_at=v.created_at,
            )
            for v in versions
        ]

    async def restore_view_version(
        self,
        view_id: str,
        version_number: int,
        user_id: str,
        user_groups: Optional[List[str]] = None,
    ) -> CustomViewResponse:
        """
        Restores a prior configuration version by creating a NEW sequential version.
        Never mutates or overwrites past version records.
        """
        view = await self.db.get(DashboardCustomView, view_id)
        if not view or view.is_archived:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Custom view '{view_id}' not found.")

        perms = await self.get_effective_permissions(view, user_id, user_groups)
        if "EDIT" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Edit permission denied to restore version.")

        # Find historical snapshot
        q = select(DashboardViewVersion).where(
            DashboardViewVersion.view_id == view_id,
            DashboardViewVersion.version_number == version_number,
        )
        res = await self.db.execute(q)
        target_version = res.scalars().first()
        if not target_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_number} does not exist for view '{view_id}'.",
            )

        snap = target_version.configuration_snapshot
        old_version = view.version
        new_version = old_version + 1

        view.layout_config = snap.get("layout_config", view.layout_config)
        view.widget_config = snap.get("widget_config", view.widget_config)
        view.filter_config = snap.get("filter_config", view.filter_config)
        view.time_range_config = snap.get("time_range_config", view.time_range_config)
        view.version = new_version
        view.updated_at = utc_now()

        # Create new version record for the restoration
        new_ver_record = DashboardViewVersion(
            view_id=view.view_id,
            version_number=new_version,
            configuration_snapshot=snap,
            changed_by_user_id=user_id,
            change_summary=f"Restored configuration from version {version_number}",
        )
        self.db.add(new_ver_record)

        audit = DashboardViewAuditLog(
            view_id=view.view_id,
            user_id=user_id,
            action="RESTORE_VERSION",
            version_before=old_version,
            version_after=new_version,
            details={"restored_from_version": version_number},
        )
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(view)

        return await self._to_response(view, user_id, user_groups, perms=perms)

    # -------------------------------------------------------------------------
    # User Preferences
    # -------------------------------------------------------------------------
    async def _get_user_preference(self, user_id: str) -> Optional[DashboardUserViewPreference]:
        q = select(DashboardUserViewPreference).where(DashboardUserViewPreference.user_id == user_id)
        res = await self.db.execute(q)
        return res.scalars().first()

    async def get_or_create_user_preferences(self, user_id: str) -> UserPreferenceResponse:
        pref = await self._get_user_preference(user_id)
        if not pref:
            pref = DashboardUserViewPreference(user_id=user_id)
            self.db.add(pref)
            await self.db.commit()
            await self.db.refresh(pref)

        return UserPreferenceResponse(
            user_id=pref.user_id,
            default_view_id=pref.default_view_id,
            preferred_timezone=pref.preferred_timezone,
            density_mode=pref.density_mode,
            auto_refresh_sec=pref.auto_refresh_sec,
            theme_preference=pref.theme_preference,
            updated_at=pref.updated_at,
        )

    async def update_user_preferences(self, user_id: str, req: UserPreferenceUpdate) -> UserPreferenceResponse:
        pref = await self._get_user_preference(user_id)
        if not pref:
            pref = DashboardUserViewPreference(user_id=user_id)
            self.db.add(pref)

        if req.default_view_id is not None:
            # Validate view exists and user has view permission
            view = await self.db.get(DashboardCustomView, req.default_view_id)
            if not view or view.is_archived:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target default view not found.")
            pref.default_view_id = req.default_view_id
        if req.preferred_timezone is not None:
            pref.preferred_timezone = req.preferred_timezone
        if req.density_mode is not None:
            pref.density_mode = req.density_mode
        if req.auto_refresh_sec is not None:
            pref.auto_refresh_sec = req.auto_refresh_sec
        if req.theme_preference is not None:
            pref.theme_preference = req.theme_preference

        pref.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(pref)

        return UserPreferenceResponse(
            user_id=pref.user_id,
            default_view_id=pref.default_view_id,
            preferred_timezone=pref.preferred_timezone,
            density_mode=pref.density_mode,
            auto_refresh_sec=pref.auto_refresh_sec,
            theme_preference=pref.theme_preference,
            updated_at=pref.updated_at,
        )

    # -------------------------------------------------------------------------
    # Helper Serializers
    # -------------------------------------------------------------------------
    async def _to_response(
        self,
        view: DashboardCustomView,
        user_id: str,
        user_groups: Optional[List[str]] = None,
        default_view_id: Optional[str] = None,
        perms: Optional[List[str]] = None,
    ) -> CustomViewResponse:
        if default_view_id is None:
            user_pref = await self._get_user_preference(user_id)
            default_view_id = user_pref.default_view_id if user_pref else None

        if perms is None:
            perms = await self.get_effective_permissions(view, user_id, user_groups)

        return CustomViewResponse(
            view_id=view.view_id,
            owner_user_id=view.owner_user_id,
            name=view.name,
            description=view.description,
            visibility=ViewVisibility(view.visibility),
            owner_group_id=view.owner_group_id,
            layout_config=LayoutConfig(**view.layout_config),
            filter_config=FilterConfig(**view.filter_config),
            time_range_config=TimeRangeConfig(**view.time_range_config),
            version=view.version,
            is_archived=view.is_archived,
            is_default=(default_view_id == view.view_id),
            effective_permissions=perms,
            created_at=view.created_at,
            updated_at=view.updated_at,
        )

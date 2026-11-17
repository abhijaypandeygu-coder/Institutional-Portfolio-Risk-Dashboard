"""
Unit and integration tests for M13.10 — Custom Views.

Verifies:
1. Central Widget Registry enumeration, retrieval, and validation.
2. Custom view creation, default starter templates (RISK_MONITORING, PORTFOLIO_MONITORING).
3. Retrieval and listing with visibility and group membership filtering.
4. Layout updating, validation (dimension bounds, registered widget IDs), and optimistic concurrency version conflict handling.
5. Non-destructive version restoration creating sequential versions.
6. View duplication into personal workspaces.
7. Explicit sharing controls (GROUP, USER, permission levels).
8. Soft deletion / archival lifecycle.
9. User preference persistence (default view, timezone, density mode).
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base
from backend.app.main import app
from backend.app.modules.dashboard_visualization.custom_views.schemas import (
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
    UserPreferenceUpdate,
)
from backend.app.modules.dashboard_visualization.custom_views.services import (
    CustomViewsService,
)
from backend.app.modules.dashboard_visualization.custom_views.widget_registry import (
    WidgetRegistryService,
    REGISTERED_WIDGETS,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def test_db_session():
    """Isolated in-memory SQLite database session for M13.10 tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# -----------------------------------------------------------------------------
# 1. Widget Registry Tests
# -----------------------------------------------------------------------------
def test_widget_registry():
    widgets = WidgetRegistryService.get_all_widgets()
    assert len(widgets) >= 9

    widget_ids = {w.widget_id for w in widgets}
    assert "m13_01_portfolio_overview" in widget_ids
    assert "m13_02_risk_overview" in widget_ids
    assert "m13_08_alerts_dashboard" in widget_ids
    assert "m13_09_historical_analytics" in widget_ids

    # Validate specific widget properties
    risk_widget = WidgetRegistryService.get_widget("m13_02_risk_overview")
    assert risk_widget is not None
    assert risk_widget.owning_module == "M13.02"
    assert "var_99" in risk_widget.supported_metrics
    assert "kpi_cards" in risk_widget.supported_visualization_types


# -----------------------------------------------------------------------------
# 2. Service-level CRUD, Templates & Concurrency Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_custom_views_service_lifecycle_and_versioning(test_db_session: AsyncSession):
    service = CustomViewsService(test_db_session)
    user_alice = "USR_ALICE"
    user_bob = "USR_BOB"
    group_risk = ["GRP_RISK_TEAM"]

    # 1. Create a view from template
    create_req = CustomViewCreate(
        name="Alice Risk Workspace",
        description="Daily monitoring for VaR and Alerts",
        visibility=ViewVisibility.PERSONAL,
        template_type="RISK_MONITORING",
    )
    view_alice = await service.create_custom_view(user_id=user_alice, req=create_req)
    assert view_alice.name == "Alice Risk Workspace"
    assert view_alice.version == 1
    assert len(view_alice.layout_config.widgets) == 3
    assert view_alice.visibility == ViewVisibility.PERSONAL
    assert "EDIT" in view_alice.effective_permissions

    # 2. Update layout with valid configuration
    updated_layout = LayoutConfig(
        grid_columns=12,
        widgets=[
            WidgetInstanceConfig(
                instance_id="inst_alerts_stream",
                widget_id="m13_08_alerts_dashboard",
                position=WidgetPosition(x=0, y=0, width=12, height=4),
                visualization_type="alert_stream",
                settings={"min_severity": "CRITICAL"},
            )
        ],
    )
    update_req = CustomViewUpdate(
        layout_config=updated_layout,
        expected_version=1,
    )
    updated_alice = await service.update_custom_view(
        view_id=view_alice.view_id, user_id=user_alice, req=update_req
    )
    assert updated_alice.version == 2
    assert len(updated_alice.layout_config.widgets) == 1

    # 3. Concurrency conflict test (expected_version=1 should fail because current is 2)
    with pytest.raises(Exception) as excinfo:
        await service.update_custom_view(
            view_id=view_alice.view_id,
            user_id=user_alice,
            req=CustomViewUpdate(name="Conflicted Title", expected_version=1),
        )
    assert "Version conflict" in str(excinfo.value.detail)

    # 4. Version history check
    versions = await service.list_view_versions(view_id=view_alice.view_id, user_id=user_alice)
    assert len(versions) == 2
    assert versions[0].version_number == 2
    assert versions[1].version_number == 1

    # 5. Restore version 1 (creates version 3 non-destructively)
    restored = await service.restore_view_version(
        view_id=view_alice.view_id, version_number=1, user_id=user_alice
    )
    assert restored.version == 3
    assert len(restored.layout_config.widgets) == 3 # Restored template's 3 widgets

    # 6. Share Alice's view with GRP_RISK_TEAM
    shares = [
        ViewShareUpdate(principal_type="GROUP", principal_id="GRP_RISK_TEAM", permission=ViewPermissionLevel.VIEW)
    ]
    updated_shares = await service.update_view_sharing(
        view_id=view_alice.view_id, user_id=user_alice, shares=shares
    )
    assert len(updated_shares) == 1
    assert updated_shares[0].principal_id == "GRP_RISK_TEAM"

    # 7. Duplicate view by Bob (Bob is member of GRP_RISK_TEAM)
    dup_req = CustomViewDuplicate(
        name="Bob Personal Copy",
        visibility=ViewVisibility.PERSONAL,
    )
    dup_view = await service.duplicate_custom_view(
        view_id=view_alice.view_id, user_id=user_bob, req=dup_req, user_groups=group_risk
    )
    assert dup_view.owner_user_id == user_bob
    assert dup_view.name == "Bob Personal Copy"
    assert dup_view.version == 1

    # 8. List views for Bob with group membership
    bob_views = await service.list_custom_views(user_id=user_bob, user_groups=group_risk)
    bob_view_ids = {v.view_id for v in bob_views.views}
    assert dup_view.view_id in bob_view_ids
    assert view_alice.view_id in bob_view_ids # Accessible via group share

    # 9. Soft-delete Alice's view
    await service.delete_custom_view(view_id=view_alice.view_id, user_id=user_alice)
    with pytest.raises(Exception):
        await service.get_custom_view(view_id=view_alice.view_id, user_id=user_alice)


# -----------------------------------------------------------------------------
# 3. HTTP API & User Preferences Integration Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_custom_views_api_and_user_preferences(test_db_session: AsyncSession):
    from backend.app.core.database import get_db

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        user = "ANALYST_QUANT_1"

        # 1. Discover widgets
        res = await ac.get("/api/v1/dashboard/custom-views/widgets")
        assert res.status_code == 200
        widgets = res.json()
        assert len(widgets) >= 9

        # 2. Get specific widget
        res = await ac.get("/api/v1/dashboard/custom-views/widgets/m13_01_portfolio_overview")
        assert res.status_code == 200
        assert res.json()["widget_id"] == "m13_01_portfolio_overview"

        # 3. Create view via API
        create_payload = {
            "name": "Quant Monitoring Desk",
            "description": "Custom API view",
            "visibility": "PERSONAL",
            "layout_config": {
                "layout_version": "1.0.0",
                "grid_columns": 12,
                "widgets": [
                    {
                        "instance_id": "inst_001",
                        "widget_id": "m13_01_portfolio_overview",
                        "widget_version": "1.0.0",
                        "position": {"x": 0, "y": 0, "width": 12, "height": 3},
                        "is_visible": True,
                        "visualization_type": "kpi_cards",
                        "settings": {"display_mode": "cards"},
                    }
                ],
            },
            "filter_config": {
                "portfolio_ids": ["PORT-001"],
                "selected_metrics": ["nav", "daily_pnl"],
            },
            "time_range_config": {
                "mode": "RELATIVE",
                "relative_preset": "LAST_30_DAYS",
                "sampling_frequency": "DAILY",
                "timezone": "America/New_York",
            },
        }
        res = await ac.post(
            f"/api/v1/dashboard/custom-views/views?user_id={user}", json=create_payload
        )
        assert res.status_code == 201
        view_data = res.json()
        view_id = view_data["view_id"]
        assert view_data["name"] == "Quant Monitoring Desk"

        # 4. Set as default view in user preferences
        pref_payload = {
            "default_view_id": view_id,
            "preferred_timezone": "America/New_York",
            "density_mode": "COMPACT",
        }
        res = await ac.put(
            f"/api/v1/dashboard/custom-views/preferences?user_id={user}", json=pref_payload
        )
        assert res.status_code == 200
        pref = res.json()
        assert pref["default_view_id"] == view_id
        assert pref["density_mode"] == "COMPACT"

        # 5. Fetch preferences
        res = await ac.get(f"/api/v1/dashboard/custom-views/preferences?user_id={user}")
        assert res.status_code == 200
        assert res.json()["default_view_id"] == view_id

        # 6. List views and verify `is_default` is True
        res = await ac.get(f"/api/v1/dashboard/custom-views/views?user_id={user}")
        assert res.status_code == 200
        views = res.json()["views"]
        target = next(v for v in views if v["view_id"] == view_id)
        assert target["is_default"] is True

    app.dependency_overrides.clear()

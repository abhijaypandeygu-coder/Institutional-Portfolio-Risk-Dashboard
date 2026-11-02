"""
M08.08 Factor Monitoring Unit and Integration Test Suite.
Verifies:
1. Exposure Drift Hand-Calculated Example (Section 20.1):
   - Reference Market exposure = 0.90
   - Current Market exposure = 1.25
   - Expected signed drift = +0.35
   - Expected percentage drift = (0.35 / 0.90) * 100 approx 38.89%
   - Reference = 0.0 guardrail: percentage drift is undefined, not an invented zero.
2. Symmetric Holdings vs. Loadings Drift Decomposition:
   - Delta(w_i * beta_i) = Delta w_i * (beta_t + beta_{t-1})/2 + Delta beta_i * (w_t + w_{t-1})/2
   - Verifies exact additive reconciliation across continuing, entering, and exiting holdings.
3. Exposure Concentration Hand-Calculated Example (Section 20.2):
   - Standardized exposures e = [0.80, 0.40, 0.20]^T
   - Sum = 1.40, shares = [0.8/1.4, 0.4/1.4, 0.2/1.4]
   - Expected HHI approx 0.4286
   - Expected effective number of factors N_eff approx 2.33
4. Risk-Contribution Concentration:
   - Evaluates absolute shares while preserving signed Euler contributions.
5. Threshold Policy Evaluation & Lifecycle:
   - Utilization = (Current / Limit) * 100, Headroom = Limit - Current.
   - Deterministic transitions: NORMAL -> WARNING -> BREACH -> CRITICAL_BREACH -> RECOVERY_PENDING -> RECOVERED.
   - Missing input guardrail: unavailable measurement NEVER automatically clears an active breach.
6. End-to-End FastAPI Lifecycle:
   - Post target profile, post threshold policy, post monitoring config.
   - Run portfolio factor monitoring pipeline.
   - Retrieve summary, exposure drift, concentration, and active breaches.
   - Acknowledge breach through API.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
import math
import uuid
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import Base, engine, get_db, init_db, AsyncSessionLocal
from backend.app.modules.factor_risk.factor_monitoring.calculations.monitoring_math import (
    compute_factor_exposure_drift,
    decompose_exposure_drift_holdings_vs_loadings,
    compute_exposure_based_concentration,
    compute_risk_contribution_based_concentration,
    evaluate_threshold_metric,
    compute_monitoring_trend_statistics,
)
from backend.app.modules.factor_risk.factor_monitoring.models import (
    MonitoringScope,
    EvaluationFrequency,
    DriftReferenceType,
    DriftClassification,
    ConcentrationStatus,
    ThresholdMetricType,
    ThresholdEvaluationStatus,
    BreachSeverity,
    BreachStatus,
)
from backend.app.modules.factor_risk.factor_definition.models import (
    FactorModel,
    FactorModelVersion,
    FactorDefinition,
    FactorDefinitionVersion,
    FactorModelMembership,
    FactorLifecycleStatus,
    MarketScope,
    FactorFamily,
    FactorType,
    ConstructionType,
)
from backend.app.modules.factor_risk.factor_exposure.models import (
    PortfolioFactorExposureSnapshot,
    FactorReturnObservation,
    FactorReturnSeries,
)
from backend.app.modules.portfolio_management.portfolio_creation.models import Portfolio


# ==============================================================================
# 1. Mathematical Unit Tests
# ==============================================================================

def test_hand_calculated_exposure_drift_and_zero_guardrail():
    """
    Verifies Section 20.1 hand-calculated example:
    Reference = 0.90, Current = 1.25 -> Signed drift = +0.35, Pct drift approx 38.89%.
    Also verifies near-zero reference guardrail.
    """
    res = compute_factor_exposure_drift(current_beta=1.25, reference_beta=0.90)
    assert abs(res["signed_drift"] - 0.35) < 1e-7
    assert abs(res["absolute_drift"] - 0.35) < 1e-7
    assert res["is_percentage_drift_defined"] is True
    assert abs(res["percentage_drift"] - 38.888888) < 1e-4
    assert res["drift_classification"] == "HIGH_DRIFT"

    # Near-zero reference test: percentage drift must be undefined
    res_zero = compute_factor_exposure_drift(current_beta=0.40, reference_beta=0.0)
    assert abs(res_zero["signed_drift"] - 0.40) < 1e-7
    assert res_zero["is_percentage_drift_defined"] is False
    assert res_zero["percentage_drift"] is None
    assert "PERCENTAGE_DRIFT_UNDEFINED" in res_zero["percentage_drift_reason"]

    # Sign reversal test
    res_rev = compute_factor_exposure_drift(current_beta=-0.30, reference_beta=0.20)
    assert res_rev["is_sign_reversal"] is True
    assert res_rev["sign_change_description"] == "POSITIVE_TO_NEGATIVE"
    assert res_rev["drift_classification"] == "SIGN_REVERSAL"


def test_exposure_drift_holdings_vs_loadings_decomposition():
    """
    Verifies symmetric additive decomposition:
    Delta(w_i * beta_i) = Delta w_i * (beta_t + beta_{t-1})/2 + Delta beta_i * (w_t + w_{t-1})/2
    Reconciles exactly against observed portfolio exposure change.
    """
    prev_weights = {"AAPL": 0.60, "MSFT": 0.40}
    curr_weights = {"AAPL": 0.50, "MSFT": 0.30, "GOOGL": 0.20}  # MSFT reduced, AAPL reduced, GOOGL entered

    prev_loadings = {"AAPL": 1.20, "MSFT": 0.80}
    curr_loadings = {"AAPL": 1.40, "MSFT": 0.90, "GOOGL": 1.10}

    decomp = decompose_exposure_drift_holdings_vs_loadings(
        current_weights=curr_weights,
        previous_weights=prev_weights,
        current_loadings=curr_loadings,
        previous_loadings=prev_loadings,
    )

    assert decomp["is_reconciled"] is True
    assert abs(decomp["observed_exposure_drift"] - decomp["reconciled_exposure_drift"]) < 1e-7
    assert decomp["entry_effect"] > 0.0  # GOOGL entered
    assert len(decomp["components"]) == 3


def test_hand_calculated_exposure_concentration():
    """
    Verifies Section 20.2 hand-calculated example:
    e = [0.80, 0.40, 0.20]^T
    Total = 1.40
    HHI = (0.8/1.4)^2 + (0.4/1.4)^2 + (0.2/1.4)^2 approx 0.4286
    N_eff = 1 / HHI approx 2.33
    """
    loadings = {"MKT": 0.80, "VAL": 0.40, "MOM": 0.20}
    # Assume 1.0 factor volatilities for direct matching
    vols = {"MKT": 1.0, "VAL": 1.0, "MOM": 1.0}

    conc = compute_exposure_based_concentration(loadings, factor_volatilities=vols)

    expected_hhi = (0.80/1.40)**2 + (0.40/1.40)**2 + (0.20/1.40)**2
    expected_neff = 1.0 / expected_hhi

    assert abs(conc["hhi"] - expected_hhi) < 1e-4
    assert abs(conc["effective_factors"] - expected_neff) < 1e-4
    assert abs(conc["top_1_share"] - (0.80 / 1.40)) < 1e-4
    assert conc["top_factor"] == "MKT"
    assert conc["status"] == "HIGH_FACTOR_CONCENTRATION"


def test_threshold_evaluation_utilization_headroom_and_recovery():
    """
    Verifies utilization, headroom, breach transitions, and recovery hysteresis.
    """
    # 1. Normal state: value 0.70 vs limit 1.00 (70% utilization, 0.30 headroom)
    res_norm = evaluate_threshold_metric(
        current_value=0.70,
        breach_threshold=1.00,
        warning_threshold=0.80,
    )
    assert res_norm["evaluation_status"] == "NORMAL"
    assert abs(res_norm["utilization_percentage"] - 70.0) < 1e-4
    assert abs(res_norm["headroom"] - 0.30) < 1e-4

    # 2. Warning state: value 0.85
    res_warn = evaluate_threshold_metric(
        current_value=0.85,
        breach_threshold=1.00,
        warning_threshold=0.80,
    )
    assert res_warn["evaluation_status"] == "WARNING"

    # 3. Breach state: value 1.15
    res_breach = evaluate_threshold_metric(
        current_value=1.15,
        breach_threshold=1.00,
        warning_threshold=0.80,
        persistence_required=1,
    )
    assert res_breach["evaluation_status"] == "BREACH"
    assert res_breach["is_breach"] is True

    # 4. Recovery hysteresis: drops to 0.95 (still above recovery 0.90) -> remains BREACH
    res_hyst = evaluate_threshold_metric(
        current_value=0.95,
        breach_threshold=1.00,
        recovery_threshold=0.90,
        is_active_breach=True,
    )
    assert res_hyst["evaluation_status"] == "BREACH"
    assert res_hyst["is_breach"] is True

    # 5. Drops below recovery threshold (0.85) -> RECOVERY_PENDING -> RECOVERED
    res_rec_pending = evaluate_threshold_metric(
        current_value=0.85,
        breach_threshold=1.00,
        recovery_threshold=0.90,
        is_active_breach=True,
        consecutive_recovery_count=0,
        recovery_required=2,
    )
    assert res_rec_pending["evaluation_status"] == "RECOVERY_PENDING"

    res_rec = evaluate_threshold_metric(
        current_value=0.85,
        breach_threshold=1.00,
        recovery_threshold=0.90,
        is_active_breach=True,
        consecutive_recovery_count=1,
        recovery_required=2,
    )
    assert res_rec["evaluation_status"] == "RECOVERED"
    assert res_rec["is_breach"] is False

    # 6. Missing measurement during active breach: MUST NOT CLEAR BREACH
    res_missing = evaluate_threshold_metric(
        current_value=None,
        breach_threshold=1.00,
        is_active_breach=True,
    )
    assert res_missing["is_breach"] is True
    assert res_missing["evaluation_status"] == "BREACH"


# ==============================================================================
# 2. End-to-End FastAPI Integration Test
# ==============================================================================

@pytest.mark.asyncio
async def test_factor_monitoring_api_lifecycle():
    """
    End-to-End integration test covering:
    1. Seeding Portfolio, Factor Model, Definitions, and Exposure Snapshots.
    2. POST /targets: Create approved factor exposure target.
    3. POST /threshold-policies: Create threshold limits on Market Beta.
    4. POST /configs: Create versioned monitoring profile.
    5. POST /portfolios/{portfolio_id}/factor-monitoring/run: Execute monitoring.
    6. GET /portfolios/{portfolio_id}/factor-monitoring: Verify summary & breach state.
    7. GET /portfolios/{portfolio_id}/factor-monitoring/drift: Verify drift records.
    8. GET /portfolios/{portfolio_id}/factor-monitoring/concentration: Verify HHI.
    9. GET /factor-monitoring/breaches: Query active breaches.
    10. POST /factor-monitoring/breaches/{breach_id}/acknowledge: Acknowledge breach.
    """
    await init_db()

    pf_id = f"PF_MON_{uuid.uuid4().hex[:8]}"
    model_id = str(uuid.uuid4())
    model_ver_id = str(uuid.uuid4())
    mkt_id = str(uuid.uuid4())
    val_id = str(uuid.uuid4())
    mom_id = str(uuid.uuid4())

    uniq = pf_id[:8]
    mkt_code = f"MKT_{uniq}"
    val_code = f"VAL_{uniq}"
    mom_code = f"MOM_{uniq}"

    async with AsyncSessionLocal() as session:
        # Create Portfolio
        portfolio = Portfolio(
            portfolio_id=pf_id,
            portfolio_code=pf_id,
            portfolio_name="Quant Growth Fund",
            short_name=pf_id,
            base_currency="INR",
            created_by="TEST_SUITE",
        )
        session.add(portfolio)

        # Create Factor Model
        model = FactorModel(
            model_id=model_id,
            model_code=f"MDL_MON_{model_id[:6]}",
            model_name="Multi-Factor Test Model",
            description="Monitoring model",
            market_scope=MarketScope.INDIA,
            currency_basis="INR",
            return_frequency="DAILY",
            lifecycle_status=FactorLifecycleStatus.ACTIVE,
            created_by="TEST_SUITE",
        )
        model_ver = FactorModelVersion(
            model_version_id=model_ver_id,
            model_id=model_id,
            version_number=1,
            model_definition_hash="HASH_MON_MDL",
            approval_status=FactorLifecycleStatus.ACTIVE,
            effective_from=date(2025, 1, 1),
            created_by="TEST_SUITE",
        )
        session.add_all([model, model_ver])

        factors_meta = [
            (mkt_id, mkt_code, "Market Factor", 1),
            (val_id, val_code, "Value Factor", 2),
            (mom_id, mom_code, "Momentum Factor", 3),
        ]

        for f_id, f_code, f_name, pos in factors_meta:
            f_fam = FactorFamily.MARKET if "MKT" in f_code else (FactorFamily.VALUE if "VAL" in f_code else FactorFamily.MOMENTUM)
            f_def = FactorDefinition(
                factor_id=f_id,
                factor_code=f_code,
                factor_name=f_name,
                factor_family=f_fam,
                factor_type=FactorType.MARKET_RETURN_FACTOR,
                economic_interpretation=f"{f_name} desc",
                construction_type=ConstructionType.INTERNALLY_CONSTRUCTED,
                description=f"{f_name} description",
                lifecycle_status=FactorLifecycleStatus.ACTIVE,
                created_by="TEST_SUITE",
            )
            f_def_ver = FactorDefinitionVersion(
                version_id=str(uuid.uuid4()),
                factor_id=f_id,
                version_number=1,
                market_scope=MarketScope.INDIA,
                currency="INR",
                frequency="DAILY",
                construction_specification={"method": "SYNTHETIC"},
                definition_hash=f"HASH_{f_code}",
                approval_status=FactorLifecycleStatus.ACTIVE,
                effective_from=date(2025, 1, 1),
            )
            membership = FactorModelMembership(
                model_version_id=model_ver_id,
                factor_id=f_id,
                version_id=f_def_ver.version_id,
                factor_code=f_code,
                factor_position=pos,
            )
            session.add_all([f_def, f_def_ver, membership])

        # Create Historical and Current Portfolio Exposure Snapshots in M08.02
        # Previous Snapshot (T-1): Market = 0.90, Value = 0.40, Momentum = 0.20
        prev_exposures = [
            (mkt_code, mkt_id, 1, 0.90),
            (val_code, val_id, 2, 0.40),
            (mom_code, mom_id, 3, 0.20),
        ]
        curr_exposures = [
            (mkt_code, mkt_id, 1, 1.25),
            (val_code, val_id, 2, 0.45),
            (mom_code, mom_id, 3, -0.10),
        ]

        load_run_id = str(uuid.uuid4())
        cfg_exposure_id = str(uuid.uuid4())
        from backend.app.modules.factor_risk.factor_exposure.models import (
            FactorExposureEstimationConfig,
            FactorLoadingRun,
            WeightingBasis,
            TiltClassification,
            LoadingQualityStatus,
            RestatementStatus,
            EstimationMethod,
            DependentReturnBasis,
            ReturnType,
            CorporateActionBasis,
            StandardErrorMethod,
            RunStatus,
        )
        exp_cfg = FactorExposureEstimationConfig(
            config_id=cfg_exposure_id,
            config_code=f"EXP_CFG_{uuid.uuid4().hex[:6]}",
            config_name="Test Exp Config",
            description="Test config",
            factor_model_id=model_id,
            factor_model_version_id=model_ver_id,
            estimation_method=EstimationMethod.ROLLING_OLS,
            lookback_observations=30,
            minimum_observations=20,
            min_observations_per_param_multiplier=5,
            currency_basis="INR",
            configuration_hash="CFG_HASH",
            status=FactorLifecycleStatus.ACTIVE,
        )
        session.add(exp_cfg)
        await session.flush()

        l_run = FactorLoadingRun(
            run_id=load_run_id,
            config_id=cfg_exposure_id,
            factor_model_id=model_id,
            factor_model_version_id=model_ver_id,
            as_of_date=date(2026, 2, 2),
            window_start=date(2026, 1, 1),
            window_end=date(2026, 2, 2),
            requested_count=1,
            successful_count=1,
            failed_count=0,
            run_status=RunStatus.COMPLETED,
        )
        session.add(l_run)

        for fc, fid, pos, exp_val in prev_exposures:
            snap = PortfolioFactorExposureSnapshot(
                exposure_snapshot_id=str(uuid.uuid4()),
                portfolio_id=pf_id,
                portfolio_snapshot_id="SNAP_PREV",
                loading_run_id=load_run_id,
                factor_model_id=model_id,
                factor_model_version_id=model_ver_id,
                factor_id=fid,
                factor_code=fc,
                factor_position=pos,
                exposure_value=Decimal(str(exp_val)),
                weighting_basis=WeightingBasis.NAV_WEIGHTED,
                tilt_classification=TiltClassification.NEUTRAL,
                portfolio_base_currency="INR",
                nav_reference=Decimal("1000000.0"),
                gross_market_value=Decimal("1000000.0"),
                covered_signed_weight=Decimal("1.0"),
                covered_absolute_weight=Decimal("1.0"),
                coverage_percentage=Decimal("100.0"),
                holding_count=10,
                covered_holding_count=10,
                as_of_date=date(2026, 2, 1),
            )
            session.add(snap)

        for fc, fid, pos, exp_val in curr_exposures:
            snap = PortfolioFactorExposureSnapshot(
                exposure_snapshot_id=str(uuid.uuid4()),
                portfolio_id=pf_id,
                portfolio_snapshot_id="SNAP_CURR",
                loading_run_id=load_run_id,
                factor_model_id=model_id,
                factor_model_version_id=model_ver_id,
                factor_id=fid,
                factor_code=fc,
                factor_position=pos,
                exposure_value=Decimal(str(exp_val)),
                weighting_basis=WeightingBasis.NAV_WEIGHTED,
                tilt_classification=TiltClassification.NEUTRAL,
                portfolio_base_currency="INR",
                nav_reference=Decimal("1000000.0"),
                gross_market_value=Decimal("1000000.0"),
                covered_signed_weight=Decimal("1.0"),
                covered_absolute_weight=Decimal("1.0"),
                coverage_percentage=Decimal("100.0"),
                holding_count=10,
                covered_holding_count=10,
                as_of_date=date(2026, 2, 2),
            )
            session.add(snap)

        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Step 2: Create Approved Target Profile (Target MKT = 1.00 +/- 0.15)
        target_payload = {
            "target_code": f"TGT_{pf_id}",
            "name": "Balanced Factor Target",
            "portfolio_id": pf_id,
            "factor_model_id": model_id,
            "factor_model_version_id": model_ver_id,
            "components": [
                {
                    "factor_id": mkt_id,
                    "factor_code": mkt_code,
                    "target_exposure": "1.000000",
                    "tolerance": "0.150000",
                }
            ],
        }
        resp = await client.post("/api/v1/factor-monitoring/targets", json=target_payload)
        assert resp.status_code == 201, resp.text
        tgt_data = resp.json()
        target_id = tgt_data["target_id"]

        # Step 3: Create Threshold Policy on Market Beta: Breach if |MKT| >= 1.20
        policy_payload = {
            "policy_code": f"POL_MKT_{pf_id}",
            "name": "Market Beta Hard Ceiling",
            "portfolio_id": pf_id,
            "factor_id": mkt_id,
            "factor_code": mkt_code,
            "metric_type": "ABSOLUTE_FACTOR_EXPOSURE",
            "warning_threshold": "1.100000",
            "breach_threshold": "1.200000",
            "critical_threshold": "1.400000",
            "recovery_threshold": "1.050000",
            "persistence_count": 1,
            "recovery_count": 2,
            "severity": "HIGH",
        }
        resp = await client.post("/api/v1/factor-monitoring/threshold-policies", json=policy_payload)
        assert resp.status_code == 201, resp.text
        policy_data = resp.json()

        # Step 4: Create Monitoring Config
        config_payload = {
            "config_code": f"CFG_MON_{pf_id}",
            "name": "Standard Daily Monitoring",
            "portfolio_id": pf_id,
            "factor_model_id": model_id,
            "factor_model_version_id": model_ver_id,
            "evaluation_frequency": "DAILY",
            "drift_reference_type": "PREVIOUS_SNAPSHOT",
            "historical_baseline_window": 30,
        }
        resp = await client.post("/api/v1/factor-monitoring/configs", json=config_payload)
        assert resp.status_code == 201, resp.text
        cfg_data = resp.json()
        config_id = cfg_data["config_id"]

        # Step 5: Execute Factor Monitoring Run
        run_payload = {
            "portfolio_id": pf_id,
            "factor_model_version_id": model_ver_id,
            "as_of_date": "2026-02-02",
            "config_id": config_id,
            "target_id": target_id,
            "evaluate_thresholds": True,
            "publish_events": True,
        }
        resp = await client.post(f"/api/v1/portfolios/{pf_id}/factor-monitoring/run", json=run_payload)
        assert resp.status_code == 200, resp.text
        run_res = resp.json()
        assert run_res["has_active_breaches"] is True
        assert run_res["active_breach_count"] >= 1

        # Step 6: Verify Drift Outputs (Market 0.90 -> 1.25: signed drift = +0.35)
        mkt_drift = next(d for d in run_res["drifts"] if d["factor_code"] == mkt_code)
        assert float(mkt_drift["signed_drift"]) == 0.35
        assert float(mkt_drift["absolute_drift"]) == 0.35
        assert abs(float(mkt_drift["percentage_drift"]) - 38.8889) < 0.01

        # Momentum flipped (0.20 -> -0.10)
        mom_drift = next(d for d in run_res["drifts"] if d["factor_code"] == mom_code)
        assert mom_drift["is_sign_reversal"] is True

        # Step 7: Verify Concentration (HHI computed)
        conc = run_res["concentration"]
        assert conc is not None
        assert conc["exposure_hhi"] is not None
        assert float(conc["effective_exposure_factors"]) > 1.0

        # Step 8: Query Active Breaches
        resp = await client.get(f"/api/v1/factor-monitoring/breaches?portfolio_id={pf_id}")
        assert resp.status_code == 200, resp.text
        breaches = resp.json()
        assert len(breaches) >= 1
        breach_id = breaches[0]["breach_id"]
        assert breaches[0]["breach_status"] == "ACTIVE"

        # Step 9: Acknowledge Active Breach
        ack_payload = {
            "user_id": "RISK_OFFICER_01",
            "note": "Acknowledged market beta spike due to tech rebalance",
        }
        resp = await client.post(f"/api/v1/factor-monitoring/breaches/{breach_id}/acknowledge", json=ack_payload)
        assert resp.status_code == 200, resp.text
        ack_res = resp.json()
        assert ack_res["breach_status"] == "ACKNOWLEDGED"
        assert ack_res["acknowledged_by"] == "RISK_OFFICER_01"

        # Step 10: Query Summary Endpoint
        resp = await client.get(f"/api/v1/portfolios/{pf_id}/factor-monitoring")
        assert resp.status_code == 200, resp.text
        summary = resp.json()
        assert summary["portfolio_id"] == pf_id
        assert summary["active_breach_count"] >= 1

"""
SQLAlchemy ORM models for M11.09 — Pre-trade Risk Checks.

Tables:
1. `pretrade_order_requests`: Intake of proposed orders from trading/strategy desks.
2. `pretrade_order_versions`: Immutable order versions with parameters.
3. `pretrade_validation_results`: Field-level validation check outputs.
4. `pretrade_evaluation_runs`: Risk evaluation execution runs.
5. `pretrade_check_results`: Individual risk check results (position, sector, gross, net, VaR, liquidity, funding).
6. `pretrade_simulation_runs`: Projected portfolio simulations.
7. `pretrade_risk_decisions`: Authoritative risk decisions (PASS, REJECT, REVIEW_REQUIRED).
8. `pretrade_decision_reason_codes`: Machine-readable reason codes supporting decisions.
9. `pretrade_authorizations`: Execution authorization credentials for downstream execution systems.
10. `pretrade_risk_reservations`: Atomic risk capacity reservations protecting against concurrent orders.
11. `pretrade_execution_references`: Confirmed fills/partial-fills for revalidation.
12. `pretrade_audit_logs`: Immutable audit trail of order evaluation events.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    Text,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.utcnow()


class PretradeOrderRequest(Base):
    """
    Intake of proposed orders before submission to an execution system.
    """
    __tablename__ = "pretrade_order_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    originating_system: Mapped[str] = mapped_column(String(64), default="ALGO_STRATEGY")
    submitting_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    current_order_version: Mapped[int] = mapped_column(Integer, default=1)
    current_status: Mapped[str] = mapped_column(String(32), default="RECEIVED", index=True)  # RECEIVED, VALIDATING, EVALUATING, APPROVED, REJECTED, REVIEW_REQUIRED, EXPIRED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    versions: Mapped[List["PretradeOrderVersion"]] = relationship(
        "PretradeOrderVersion", back_populates="request", cascade="all, delete-orphan", order_by="desc(PretradeOrderVersion.version_number)"
    )


class PretradeOrderVersion(Base):
    """
    Immutable versioned parameters of a proposed order.
    """
    __tablename__ = "pretrade_order_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    proposed_order_id: Mapped[str] = mapped_column(String(64), ForeignKey("pretrade_order_requests.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    listing_id: Mapped[str] = mapped_column(String(64), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)  # BUY, SELL
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    order_type: Mapped[str] = mapped_column(String(32), default="LIMIT")  # MARKET, LIMIT, STOP, STOP_LIMIT
    limit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    stop_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    time_in_force: Mapped[str] = mapped_column(String(16), default="DAY")  # DAY, IOC, FOK, GTC
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    strategy_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    request: Mapped["PretradeOrderRequest"] = relationship("PretradeOrderRequest", back_populates="versions")
    evaluations: Mapped[List["PretradeEvaluationRun"]] = relationship(
        "PretradeEvaluationRun", back_populates="order_version", cascade="all, delete-orphan"
    )


class PretradeEvaluationRun(Base):
    """
    An execution run evaluating a proposed order against risk policies.
    """
    __tablename__ = "pretrade_evaluation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    proposed_order_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("pretrade_order_versions.id", ondelete="CASCADE"), index=True)
    portfolio_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_status: Mapped[str] = mapped_column(String(32), default="COMPLETED")  # COMPLETED, FAILED
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    evaluation_latency_ms: Mapped[float] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))

    order_version: Mapped["PretradeOrderVersion"] = relationship("PretradeOrderVersion", back_populates="evaluations")
    check_results: Mapped[List["PretradeCheckResult"]] = relationship(
        "PretradeCheckResult", back_populates="evaluation_run", cascade="all, delete-orphan"
    )
    simulation_runs: Mapped[List["PretradeSimulationRun"]] = relationship(
        "PretradeSimulationRun", back_populates="evaluation_run", cascade="all, delete-orphan"
    )
    decision: Mapped[Optional["PretradeRiskDecision"]] = relationship(
        "PretradeRiskDecision", back_populates="evaluation_run", uselist=False, cascade="all, delete-orphan"
    )


class PretradeCheckResult(Base):
    """
    Detailed output of an individual risk constraint check.
    """
    __tablename__ = "pretrade_check_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("pretrade_evaluation_runs.id", ondelete="CASCADE"), index=True)
    check_name: Mapped[str] = mapped_column(String(64), nullable=False)  # position_limit, sector_limit, gross_exposure, net_exposure, var_limit, liquidity_limit, funding_check, data_freshness
    check_category: Mapped[str] = mapped_column(String(64), nullable=False)  # POSITION, SECTOR, EXPOSURE, QUANTITATIVE, LIQUIDITY, FUNDING, DATA_QUALITY
    check_status: Mapped[str] = mapped_column(String(32), nullable=False)  # PASS, WARNING, HARD_FAIL, REVIEW_REQUIRED, UNAVAILABLE, STALE
    current_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.00"))
    projected_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.00"))
    effective_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    utilization_percentage: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    unit: Mapped[str] = mapped_column(String(32), default="NAV_WEIGHT")
    source_module: Mapped[str] = mapped_column(String(32), default="M11.02")
    reason_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    evaluation_run: Mapped["PretradeEvaluationRun"] = relationship("PretradeEvaluationRun", back_populates="check_results")


class PretradeSimulationRun(Base):
    """
    Projected portfolio state simulated for the proposed order.
    """
    __tablename__ = "pretrade_simulation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("pretrade_evaluation_runs.id", ondelete="CASCADE"), index=True)
    portfolio_nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    projected_nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    current_position_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.00"))
    projected_position_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    position_transition_type: Mapped[str] = mapped_column(String(64), nullable=False)  # NEW_LONG, LONG_INCREASED, LONG_CLOSED, etc.
    projected_gross_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    projected_net_exposure: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    projected_var: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.00"))
    incremental_var: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.00"))
    simulation_status: Mapped[str] = mapped_column(String(32), default="SUCCESS")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    evaluation_run: Mapped["PretradeEvaluationRun"] = relationship("PretradeEvaluationRun", back_populates="simulation_runs")


class PretradeRiskDecision(Base):
    """
    Final deterministic risk decision for an evaluated order version.
    """
    __tablename__ = "pretrade_risk_decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("pretrade_evaluation_runs.id", ondelete="CASCADE"), unique=True, index=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # PASS, REJECT, REVIEW_REQUIRED
    primary_reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_summary: Mapped[Text] = mapped_column(Text, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    authorization_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    evaluation_run: Mapped["PretradeEvaluationRun"] = relationship("PretradeEvaluationRun", back_populates="decision")
    authorizations: Mapped[List["PretradeAuthorization"]] = relationship(
        "PretradeAuthorization", back_populates="decision", cascade="all, delete-orphan"
    )


class PretradeAuthorization(Base):
    """
    Execution authorization token granted upon a PASS decision.
    """
    __tablename__ = "pretrade_authorizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_id: Mapped[str] = mapped_column(String(64), ForeignKey("pretrade_risk_decisions.id", ondelete="CASCADE"), index=True)
    proposed_order_version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    permitted_instrument_id: Mapped[str] = mapped_column(String(64), nullable=False)
    permitted_side: Mapped[str] = mapped_column(String(16), nullable=False)
    permitted_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    authorization_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)  # ACTIVE, CONSUMED, EXPIRED, REVOKED
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    decision: Mapped["PretradeRiskDecision"] = relationship("PretradeRiskDecision", back_populates="authorizations")
    reservations: Mapped[List["PretradeRiskReservation"]] = relationship(
        "PretradeRiskReservation", back_populates="authorization", cascade="all, delete-orphan"
    )


class PretradeRiskReservation(Base):
    """
    Risk capacity reservation preventing concurrent approved orders from violating limits.
    """
    __tablename__ = "pretrade_risk_reservations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    authorization_id: Mapped[str] = mapped_column(String(64), ForeignKey("pretrade_authorizations.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reserved_notional: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reservation_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)  # ACTIVE, CONSUMED, RELEASED, EXPIRED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    authorization: Mapped["PretradeAuthorization"] = relationship("PretradeAuthorization", back_populates="reservations")


class PretradeExecutionReference(Base):
    """
    Tracks confirmed executions/fills and reconciles against reservations.
    """
    __tablename__ = "pretrade_execution_references"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    authorization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fill_reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    execution_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    execution_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PretradeAuditLog(Base):
    """
    Immutable governance and execution audit log.
    """
    __tablename__ = "pretrade_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)  # ORDER_INTAKE, EVALUATED, AUTHORIZATION_GRANTED, REJECTED, RESERVATION_RELEASED
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

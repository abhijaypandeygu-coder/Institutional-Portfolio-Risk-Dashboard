"""SQLAlchemy 2.x Database engine, sessionmaker, and Base."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from backend.app.core.config import settings

engine_kwargs = {
    "echo": False,
    "future": True,
}

if "sqlite" in settings.DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()


async def init_db() -> None:
    """Initialize database tables."""
    # Ensure all models are imported before creating tables
    import backend.app.modules.feed_registry.models  # noqa: F401
    import backend.app.modules.market_data_ingestion.persistence.models  # noqa: F401
    import backend.app.modules.market_data_quality.missing_data.models  # noqa: F401
    import backend.app.modules.market_data_quality.price_validation.models  # noqa: F401
    import backend.app.modules.market_data_quality.timestamp_validation.models  # noqa: F401
    import backend.app.modules.market_data_quality.order_book.models  # noqa: F401
    import backend.app.modules.market_data_quality.duplicate_detection.models  # noqa: F401
    import backend.app.modules.market_data_quality.consistency.models  # noqa: F401
    import backend.app.modules.market_data_quality.quality_scoring.models  # noqa: F401
    import backend.app.modules.market_data_quality.exception_management.models  # noqa: F401
    import backend.app.modules.instrument_reference_data.instrument_master.models  # noqa: F401
    import backend.app.modules.instrument_reference_data.security_classification.models  # noqa: F401
    import backend.app.modules.instrument_reference_data.corporate_actions.models  # noqa: F401
    import backend.app.modules.instrument_reference_data.trading_calendar.models  # noqa: F401
    import backend.app.modules.instrument_reference_data.price_reference.models  # noqa: F401
    import backend.app.modules.instrument_reference_data.instrument_lifecycle.models  # noqa: F401
    import backend.app.modules.instrument_reference_data.instrument_mapping.models  # noqa: F401
    import backend.app.modules.portfolio_management.portfolio_creation.models  # noqa: F401
    import backend.app.modules.portfolio_management.position_management.models  # noqa: F401
    import backend.app.modules.portfolio_management.position_valuation.models  # noqa: F401
    import backend.app.modules.portfolio_management.cash_management.models  # noqa: F401
    import backend.app.modules.portfolio_management.transaction_management.models  # noqa: F401
    import backend.app.modules.portfolio_management.portfolio_reconciliation.models  # noqa: F401
    import backend.app.modules.portfolio_management.portfolio_history.models  # noqa: F401
    import backend.app.modules.portfolio_management.multi_portfolio_management.models  # noqa: F401
    import backend.app.modules.risk_management.gross_exposure.models  # noqa: F401
    import backend.app.modules.risk_management.net_exposure.models  # noqa: F401
    import backend.app.modules.risk_management.sector_exposure.models  # noqa: F401
    import backend.app.modules.risk_management.instrument_exposure.models  # noqa: F401
    import backend.app.modules.instrument_reference_data.geographic_classification.models  # noqa: F401
    import backend.app.modules.risk_management.geographic_exposure.models  # noqa: F401
    import backend.app.modules.risk_management.concentration_analytics.models  # noqa: F401
    import backend.app.modules.risk_management.portfolio_allocation.models  # noqa: F401
    import backend.app.modules.risk_management.exposure_limits.models  # noqa: F401
    import backend.app.modules.market_risk.historical_volatility.models  # noqa: F401
    import backend.app.modules.market_risk.value_at_risk.models  # noqa: F401
    import backend.app.modules.market_risk.expected_shortfall.models  # noqa: F401
    import backend.app.modules.market_risk.drawdown_analytics.models  # noqa: F401
    import backend.app.modules.market_risk.correlation.models  # noqa: F401
    import backend.app.modules.market_risk.covariance.models  # noqa: F401
    import backend.app.modules.market_risk.beta.models  # noqa: F401
    import backend.app.modules.market_risk.sharpe_sortino.models  # noqa: F401
    import backend.app.modules.market_risk.risk_contribution.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency providing a transaction-managed async session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

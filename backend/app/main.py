"""
Institutional Portfolio Risk Dashboard - Main Backend Application Entrypoint.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.modules.feed_registry.router import router as feed_registry_router
from backend.app.modules.market_data_ingestion.router import router as market_data_router
from backend.app.modules.market_data_quality.missing_data.router import router as missing_data_router
from backend.app.modules.market_data_quality.price_validation.router import router as price_validation_router
from backend.app.modules.market_data_quality.timestamp_validation.router import router as timestamp_validation_router
from backend.app.modules.market_data_quality.order_book.router import router as order_book_router
from backend.app.modules.market_data_quality.duplicate_detection.router import router as duplicate_detection_router
from backend.app.modules.market_data_quality.consistency.router import router as consistency_router
from backend.app.modules.market_data_quality.quality_scoring.router import router as quality_scoring_router
from backend.app.modules.market_data_quality.exception_management.router import router as exception_management_router
from backend.app.modules.instrument_reference_data.instrument_master.router import router as instrument_master_router
from backend.app.modules.instrument_reference_data.security_classification.router import router as security_classification_router
from backend.app.modules.instrument_reference_data.corporate_actions.router import router as corporate_actions_router
from backend.app.modules.instrument_reference_data.trading_calendar.router import router as trading_calendar_router
from backend.app.modules.instrument_reference_data.price_reference.router import router as price_reference_router
from backend.app.modules.instrument_reference_data.instrument_lifecycle.router import router as instrument_lifecycle_router
from backend.app.modules.instrument_reference_data.instrument_mapping.router import router as instrument_mapping_router
from backend.app.modules.portfolio_management.portfolio_creation.router import router as portfolio_creation_router
from backend.app.modules.portfolio_management.position_management.router import router as position_management_router
from backend.app.modules.portfolio_management.position_valuation.router import router as position_valuation_router
from backend.app.modules.portfolio_management.cash_management.router import router as cash_management_router
from backend.app.modules.portfolio_management.transaction_management.router import router as transaction_management_router
from backend.app.modules.portfolio_management.portfolio_reconciliation.router import router as portfolio_reconciliation_router
from backend.app.modules.portfolio_management.portfolio_history.router import router as portfolio_history_router
from backend.app.modules.portfolio_management.multi_portfolio_management.router import router as multi_portfolio_management_router
from backend.app.modules.risk_management.gross_exposure.router import router as gross_exposure_router
from backend.app.modules.risk_management.net_exposure.router import router as net_exposure_router
from backend.app.modules.risk_management.sector_exposure.router import router as sector_exposure_router
from backend.app.modules.risk_management.instrument_exposure.router import router as instrument_exposure_router
from backend.app.modules.risk_management.geographic_exposure.router import router as geographic_exposure_router
from backend.app.modules.risk_management.concentration_analytics.router import router as concentration_analytics_router
from backend.app.modules.risk_management.portfolio_allocation.router import router as portfolio_allocation_router
from backend.app.modules.risk_management.exposure_limits.router import router as exposure_limits_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure database schema and tables are initialized
    await init_db()
    yield
    # Shutdown logic (e.g. clean up pools, notify services)


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Institutional Portfolio Risk Dashboard - High-Frequency Trading & Risk Architecture",
    lifespan=lifespan,
)

# Enable CORS for frontend dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(feed_registry_router, prefix="/api/v1")
app.include_router(market_data_router, prefix="/api/v1")
app.include_router(missing_data_router, prefix="/api/v1")
app.include_router(price_validation_router, prefix="/api/v1")
app.include_router(timestamp_validation_router, prefix="/api/v1")
app.include_router(order_book_router, prefix="/api/v1")
app.include_router(duplicate_detection_router, prefix="/api/v1")
app.include_router(consistency_router, prefix="/api/v1")
app.include_router(quality_scoring_router, prefix="/api/v1")
app.include_router(exception_management_router, prefix="/api/v1")
app.include_router(instrument_master_router, prefix="/api/v1")
app.include_router(security_classification_router, prefix="/api/v1")
app.include_router(corporate_actions_router, prefix="/api/v1")
app.include_router(trading_calendar_router, prefix="/api/v1")
app.include_router(price_reference_router, prefix="/api/v1")
app.include_router(instrument_lifecycle_router, prefix="/api/v1")
app.include_router(instrument_mapping_router, prefix="/api/v1")
app.include_router(portfolio_creation_router, prefix="/api/v1")
app.include_router(position_management_router, prefix="/api/v1")
app.include_router(position_valuation_router, prefix="/api/v1")
app.include_router(cash_management_router)
app.include_router(transaction_management_router)
app.include_router(portfolio_reconciliation_router)
app.include_router(portfolio_history_router)
app.include_router(multi_portfolio_management_router)
app.include_router(gross_exposure_router)
app.include_router(net_exposure_router)
app.include_router(sector_exposure_router)
app.include_router(instrument_exposure_router, prefix="/api/v1")
app.include_router(geographic_exposure_router, prefix="/api/v1")
app.include_router(concentration_analytics_router, prefix="/api/v1")
app.include_router(portfolio_allocation_router, prefix="/api/v1")
app.include_router(exposure_limits_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def root_health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "module": "M01 - Feed Registry & Configuration",
        "modules": [
            "M01 - Feed Registry & Configuration",
            "M02 - Market Data Ingestion Engine (Alpha Vantage + Simulator)",
            "M03.01 - Missing Data Detection",
            "M03.02 - Price Validation Engine",
            "M03.03 - Timestamp Validation Engine",
            "M03.04 - Order Book Validation Engine",
            "M03.05 - Duplicate Detection & Idempotency Engine",
            "M03.06 - Data Consistency Engine",
            "M03.07 - Quality Scoring & Use Eligibility Engine",
            "M03.08 - Exception Management Engine",
            "M04.01 - Instrument Master Engine",
            "M04.02 - Security Classification Engine",
            "M04.03 - Corporate Actions Engine",
            "M04.04 - Trading Calendar Engine",
            "M04.05 - Price Reference Engine",
            "M04.06 - Instrument Lifecycle Engine",
            "M04.07 - Instrument Mapping Engine",
            "M05.01 - Portfolio Creation Engine",
            "M05.02 - Position Management Engine",
            "M05.03 - Position Valuation Engine",
            "M05.04 - Cash Management Engine",
            "M05.05 - Transaction Management Engine",
            "M05.06 - Portfolio Reconciliation Engine",
            "M05.07 - Portfolio History Engine",
            "M05.08 - Multi-Portfolio Management Engine",
            "M06.01 - Gross Exposure Engine",
            "M06.02 - Net Exposure Engine",
            "M06.03 - Sector Exposure Engine",
            "M06.04 - Instrument Exposure Engine",
            "M06.05 - Geographic Exposure Engine",
            "M06.06 - Concentration Analytics Engine",
            "M06.07 - Portfolio Allocation Engine",
            "M06.08 - Exposure Limits Engine",
        ],
    }

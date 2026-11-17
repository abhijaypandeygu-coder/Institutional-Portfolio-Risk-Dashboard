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
from backend.app.modules.market_risk.historical_volatility.router import router as historical_volatility_router
from backend.app.modules.market_risk.value_at_risk.router import router as var_router, config_router as var_config_router
from backend.app.modules.market_risk.expected_shortfall.router import (
    router as es_router,
    group_router as es_group_router,
    config_router as es_config_router,
)
from backend.app.modules.market_risk.drawdown_analytics.router import (
    global_router as drawdown_global_router,
    portfolio_router as drawdown_portfolio_router,
    group_router as drawdown_group_router,
)
from backend.app.modules.market_risk.correlation.router import (
    router as correlation_router,
    portfolio_router as correlation_portfolio_router,
)
from backend.app.modules.market_risk.covariance.router import (
    router as covariance_router,
    portfolio_router as covariance_portfolio_router,
)
from backend.app.modules.market_risk.beta.router import (
    router as beta_router,
    portfolio_router as beta_portfolio_router,
)
from backend.app.modules.market_risk.sharpe_sortino.router import (
    router as sharpe_sortino_router,
    portfolio_router as sharpe_sortino_portfolio_router,
)
from backend.app.modules.market_risk.risk_contribution.router import (
    router as risk_contribution_router,
    portfolio_nested_router as risk_contribution_portfolio_router,
)
from backend.app.modules.market_risk.risk_forecasting.router import (
    router as risk_forecasting_router,
    portfolio_nested_router as risk_forecasting_portfolio_router,
)
from backend.app.modules.factor_risk.factor_definition.router import (
    router as factor_definition_router,
    models_router as factor_models_router,
)
from backend.app.modules.factor_risk.factor_exposure.router import (
    router as factor_exposure_router,
    portfolio_router as factor_exposure_portfolio_router,
    instrument_router as factor_exposure_instrument_router,
)
from backend.app.modules.factor_risk.factor_sensitivity.router import (
    router as factor_sensitivity_router,
)
from backend.app.modules.factor_risk.factor_attribution.router import (
    router as factor_attribution_router,
)
from backend.app.modules.factor_risk.systematic_risk.router import (
    router as systematic_risk_router,
)
from backend.app.modules.factor_risk.idiosyncratic_risk.router import (
    router as idiosyncratic_risk_router,
)
from backend.app.modules.factor_risk.factor_correlation.router import (
    router as factor_correlation_router,
)
from backend.app.modules.factor_risk.factor_monitoring.router import (
    router as factor_monitoring_router,
    portfolio_router as factor_monitoring_portfolio_router,
)
from backend.app.modules.market_microstructure.bid_ask_spread.router import (
    router as bid_ask_spread_router,
)
from backend.app.modules.market_microstructure.order_book_depth.router import (
    router as order_book_depth_router,
)
from backend.app.modules.market_microstructure.liquidity_estimation.router import (
    router as liquidity_estimation_router,
)
from backend.app.modules.market_microstructure.market_impact.router import (
    router as market_impact_router,
)
from backend.app.modules.market_microstructure.slippage_estimation.router import (
    router as slippage_estimation_router,
)
from backend.app.modules.market_microstructure.liquidity_stress_testing.router import (
    router as liquidity_stress_testing_router,
)
from backend.app.modules.market_microstructure.position_liquidation.router import (
    router as position_liquidation_router,
)
from backend.app.modules.market_microstructure.order_book_imbalance.router import (
    router as order_book_imbalance_router,
)
from backend.app.modules.market_microstructure.microstructure_monitoring.router import (
    router as microstructure_monitoring_router,
)
from backend.app.modules.scenario_analysis.historical_scenarios.router import (
    router as historical_scenarios_router,
)
from backend.app.modules.scenario_analysis.hypothetical_scenarios.router import (
    router as hypothetical_scenarios_router,
)
from backend.app.modules.scenario_analysis.market_crash.router import (
    router as market_crash_router,
)
from backend.app.modules.scenario_analysis.sector_shock.router import (
    router as sector_shock_router,
)
from backend.app.modules.scenario_analysis.correlation_shock.router import (
    router as correlation_shock_router,
)
from backend.app.modules.scenario_analysis.liquidity_stress.router import (
    router as liquidity_stress_router,
)
from backend.app.modules.scenario_analysis.monte_carlo.router import (
    router as monte_carlo_router,
)
from backend.app.modules.scenario_analysis.scenario_comparison.router import (
    router as scenario_comparison_router,
)
from backend.app.modules.scenario_analysis.loss_attribution.router import (
    router as loss_attribution_router,
)
from backend.app.modules.risk_limits.portfolio_risk_limits.router import (
    router as portfolio_risk_limits_router,
)
from backend.app.modules.risk_limits.position_limits.router import (
    router as position_limits_router,
)
from backend.app.modules.risk_limits.sector_limits.router import (
    router as sector_limits_router,
)
from backend.app.modules.risk_limits.liquidity_limits.router import (
    router as liquidity_limits_router,
)
from backend.app.modules.risk_limits.dynamic_limits.router import (
    router as dynamic_limits_router,
)
from backend.app.modules.risk_limits.breach_detection.router import (
    router as breach_detection_router,
)
from backend.app.modules.risk_limits.breach_classification.router import (
    router as breach_classification_router,
)
from backend.app.modules.risk_limits.risk_escalation.router import (
    router as risk_escalation_router,
)
from backend.app.modules.risk_limits.pretrade_risk_checks.router import (
    router as pretrade_risk_checks_router,
)
from backend.app.modules.risk_alerts.router import (
    router as risk_alerts_router,
)
from backend.app.modules.risk_alerts.market_alerts.router import (
    router as market_alerts_router,
)
from backend.app.modules.risk_alerts.liquidity_alerts.router import (
    router as liquidity_alerts_router,
)
from backend.app.modules.risk_alerts.portfolio_alerts.router import (
    router as portfolio_alerts_router,
)
from backend.app.modules.risk_alerts.alert_prioritization.router import (
    router as alert_prioritization_router,
)
from backend.app.modules.risk_alerts.alert_management.router import (
    router as alert_management_router,
)
from backend.app.modules.risk_alerts.notification_channels.router import (
    router as notification_channels_router,
)
from backend.app.modules.risk_alerts.alert_history.router import (
    router as alert_history_router,
)
from backend.app.modules.dashboard_visualization.portfolio_overview.router import (
    router as portfolio_overview_router,
)
from backend.app.modules.dashboard_visualization.risk_overview.router import (
    router as risk_overview_router,
)
from backend.app.modules.dashboard_visualization.exposure_dashboard.router import (
    router as exposure_dashboard_router,
)
from backend.app.modules.dashboard_visualization.risk_heatmaps.router import (
    router as risk_heatmaps_router,
)
from backend.app.modules.dashboard_visualization.correlation_dashboard.router import (
    router as correlation_dashboard_router,
)
from backend.app.modules.dashboard_visualization.liquidity_dashboard.router import (
    router as liquidity_dashboard_router,
)
from backend.app.modules.dashboard_visualization.stress_dashboard.router import (
    router as stress_dashboard_router,
)
from backend.app.modules.dashboard_visualization.alerts_dashboard.router import (
    router as alerts_dashboard_router,
)
from backend.app.modules.dashboard_visualization.historical_analytics.router import (
    router as historical_analytics_router,
)
from backend.app.modules.dashboard_visualization.custom_views.router import (
    router as custom_views_router,
)
from backend.app.modules.reporting_attribution_audit.daily_risk_reports.router import (
    router as daily_risk_reports_router,
)
from backend.app.modules.reporting_attribution_audit.portfolio_performance.router import (
    router as portfolio_performance_router,
)
from backend.app.modules.reporting_attribution_audit.risk_attribution.router import (
    router as risk_attribution_router,
)
from backend.app.modules.reporting_attribution_audit.stress_testing.router import (
    router as stress_reports_router,
)
from backend.app.modules.reporting_attribution_audit.liquidity.router import (
    router as liquidity_reports_router,
)
from backend.app.modules.reporting_attribution_audit.export_engine.router import (
    router as export_engine_router,
)


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
app.include_router(historical_volatility_router, prefix="/api/v1")
app.include_router(var_router, prefix="/api/v1")
app.include_router(var_config_router, prefix="/api/v1")
app.include_router(es_router)
app.include_router(es_group_router)
app.include_router(es_config_router)
app.include_router(drawdown_global_router)
app.include_router(drawdown_portfolio_router)
app.include_router(drawdown_group_router)
app.include_router(correlation_router, prefix="/api/v1/market-risk/correlation", tags=["M07.05 - Correlation Analysis"])
app.include_router(correlation_portfolio_router, prefix="/api/v1/portfolios", tags=["M07.05 - Portfolio Correlation"])
app.include_router(covariance_router, prefix="/api/v1/market-risk/covariance", tags=["M07.06 - Covariance Analysis"])
app.include_router(covariance_portfolio_router, prefix="/api/v1/portfolios", tags=["M07.06 - Portfolio Covariance"])
app.include_router(beta_router, prefix="/api/v1/market-risk/beta", tags=["M07.07 - Portfolio Beta"])
app.include_router(beta_portfolio_router, prefix="/api/v1/portfolios", tags=["M07.07 - Portfolio Beta"])
app.include_router(sharpe_sortino_router, prefix="/api/v1/market-risk/ratios", tags=["M07.08 - Sharpe & Sortino Ratios"])
app.include_router(sharpe_sortino_portfolio_router, prefix="/api/v1/portfolios", tags=["M07.08 - Portfolio Ratios"])
app.include_router(risk_contribution_router, tags=["M07.09 - Risk Contribution"])
app.include_router(risk_contribution_portfolio_router, tags=["M07.09 - Portfolio Risk Attribution"])
app.include_router(risk_forecasting_router, tags=["M07.10 - Risk Forecasting"])
app.include_router(risk_forecasting_portfolio_router, tags=["M07.10 - Portfolio Risk Forecasting"])
app.include_router(factor_definition_router, tags=["M08.01 - Factor Definition"])
app.include_router(factor_models_router, tags=["M08.01 - Factor Models"])
app.include_router(factor_exposure_router, tags=["M08.02 - Factor Exposure"])
app.include_router(factor_exposure_portfolio_router, tags=["M08.02 - Portfolio Factor Exposure"])
app.include_router(factor_exposure_instrument_router, tags=["M08.02 - Instrument Factor Exposure"])
app.include_router(factor_sensitivity_router, tags=["M08.03 - Factor Sensitivity"])
app.include_router(factor_attribution_router, tags=["M08.04 - Factor Attribution"])
app.include_router(systematic_risk_router, tags=["M08.05 - Systematic Risk"])
app.include_router(idiosyncratic_risk_router, tags=["M08.06 - Idiosyncratic Risk"])
app.include_router(factor_correlation_router, tags=["M08.07 - Factor Correlation"])
app.include_router(factor_monitoring_router, tags=["M08.08 - Factor Monitoring"])
app.include_router(factor_monitoring_portfolio_router, tags=["M08.08 - Portfolio Factor Monitoring"])
app.include_router(bid_ask_spread_router, tags=["M09.01 - Bid-Ask Spread Analytics"])
app.include_router(order_book_depth_router, tags=["M09.02 - Order Book Depth Analytics"])
app.include_router(liquidity_estimation_router, prefix="/api/v1/market-microstructure", tags=["M09.03 - Liquidity Estimation Analytics"])
app.include_router(market_impact_router, prefix="/api/v1/market-microstructure", tags=["M09.04 - Market Impact Analytics"])
app.include_router(slippage_estimation_router, tags=["M09.05 - Slippage Estimation Analytics"])
app.include_router(liquidity_stress_testing_router, tags=["M09.06 - Liquidity Stress Testing Analytics"])
app.include_router(position_liquidation_router, tags=["M09.07 - Position Liquidation Analytics"])
app.include_router(order_book_imbalance_router, tags=["M09.08 - Order Book Imbalance Analytics"])
app.include_router(microstructure_monitoring_router, tags=["M09.09 - Microstructure Monitoring"])
app.include_router(historical_scenarios_router, tags=["M10.01 - Historical Scenarios"])
app.include_router(hypothetical_scenarios_router, tags=["M10.02 - Hypothetical Scenarios"])
app.include_router(market_crash_router, tags=["M10.03 - Market Crash Simulation"])
app.include_router(sector_shock_router, tags=["M10.04 - Sector Shock Simulation"])
app.include_router(correlation_shock_router, tags=["M10.05 - Correlation Shock"])
app.include_router(liquidity_stress_router, tags=["M10.06 - Liquidity Stress Testing"])
app.include_router(monte_carlo_router, tags=["M10.07 - Monte Carlo Scenarios"])
app.include_router(scenario_comparison_router, tags=["M10.08 - Scenario Comparison"])
app.include_router(loss_attribution_router, tags=["M10.09 - Stress Loss Attribution"])
app.include_router(portfolio_risk_limits_router, tags=["M11.01 - Portfolio Risk Limits"])
app.include_router(position_limits_router, tags=["M11.02 - Position Limits"])
app.include_router(sector_limits_router, tags=["M11.03 - Sector Limits"])
app.include_router(liquidity_limits_router, tags=["M11.04 - Liquidity Limits"])
app.include_router(dynamic_limits_router, tags=["M11.05 - Dynamic Limits"])
app.include_router(breach_detection_router, tags=["M11.06 - Breach Detection"])
app.include_router(breach_classification_router, tags=["M11.07 - Breach Classification"])
app.include_router(risk_escalation_router, tags=["M11.08 - Risk Escalation"])
app.include_router(pretrade_risk_checks_router, tags=["M11.09 - Pre-trade Risk Checks"])
app.include_router(risk_alerts_router, tags=["M12 - Risk Alerts & Notification Engine"])
app.include_router(market_alerts_router, tags=["M12.02 - Market Alerts Engine"])
app.include_router(liquidity_alerts_router, tags=["M12.03 - Liquidity Alerts Engine"])
app.include_router(portfolio_alerts_router, tags=["M12.04 - Portfolio Alerts Engine"])
app.include_router(alert_prioritization_router, prefix="/api/v1", tags=["M12.05 - Alert Prioritization Engine"])
app.include_router(alert_management_router, prefix="/api/v1", tags=["M12.06 - Alert Management Engine"])
app.include_router(notification_channels_router, prefix="/api/v1", tags=["M12.07 - Notification Channels Engine"])
app.include_router(alert_history_router, prefix="/api/v1", tags=["M12.08 - Alert History Engine"])
app.include_router(portfolio_overview_router, prefix="/api/v1", tags=["M13.01 - Portfolio Overview Dashboard"])
app.include_router(risk_overview_router, prefix="/api/v1/dashboard/portfolios", tags=["M13.02 - Risk Overview Dashboard"])
app.include_router(exposure_dashboard_router, prefix="/api/v1/dashboard/portfolios", tags=["M13.03 - Exposure Dashboard"])
app.include_router(risk_heatmaps_router, prefix="/api/v1/dashboard/portfolios", tags=["M13.04 - Risk Heatmaps"])
app.include_router(correlation_dashboard_router, prefix="/api/v1/dashboard", tags=["M13.05 - Correlation Dashboard"])
app.include_router(liquidity_dashboard_router, tags=["M13.06 - Liquidity Dashboard"])
app.include_router(stress_dashboard_router, tags=["M13.07 - Stress Testing Dashboard"])
app.include_router(alerts_dashboard_router, tags=["M13.08 - Alerts Dashboard"])
app.include_router(historical_analytics_router, prefix="/api/v1/dashboard", tags=["M13.09 - Historical Analytics"])
app.include_router(custom_views_router, prefix="/api/v1/dashboard", tags=["M13.10 - Custom Views"])
app.include_router(daily_risk_reports_router, prefix="/api/v1", tags=["M14.01 - Daily Risk Reports"])
app.include_router(portfolio_performance_router, prefix="/api/v1", tags=["M14.02 - Portfolio Performance Reports"])
app.include_router(risk_attribution_router, prefix="/api/v1/reports/risk-attribution", tags=["M14.03 - Risk Attribution Reports"])
app.include_router(stress_reports_router, prefix="/api/v1/reports/stress", tags=["M14.04 - Stress Testing Reports"])
app.include_router(liquidity_reports_router, prefix="/api/v1/reports/liquidity", tags=["M14.05 - Liquidity Reports"])
app.include_router(export_engine_router, prefix="/api/v1", tags=["M14.06 - Export Engine"])


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
            "M07.01 - Historical Volatility Engine",
            "M07.02 - Value at Risk (VaR) Engine",
            "M07.03 - Expected Shortfall (ES) Engine",
            "M07.04 - Drawdown Analytics Engine",
            "M07.05 - Correlation Analysis Engine",
            "M07.06 - Covariance Analysis Engine",
            "M07.07 - Portfolio Beta Engine",
            "M07.08 - Sharpe & Sortino Ratios Engine",
            "M07.09 - Risk Contribution Engine",
            "M07.10 - Risk Forecasting Engine",
            "M08.01 - Factor Definition Engine",
            "M08.02 - Factor Exposure Engine",
            "M08.03 - Factor Sensitivity Engine",
            "M08.04 - Factor Attribution Engine",
            "M08.05 - Systematic Risk Engine",
            "M08.06 - Idiosyncratic Risk Engine",
            "M08.07 - Factor Correlation Engine",
            "M08.08 - Factor Monitoring Engine",
            "M09.01 - Bid-Ask Spread Engine",
            "M09.02 - Order Book Depth Engine",
            "M09.03 - Liquidity Estimation Engine",
            "M09.04 - Market Impact Engine",
            "M09.05 - Slippage Estimation Engine",
            "M09.06 - Liquidity Stress Testing Engine",
            "M09.07 - Position Liquidation Engine",
            "M09.08 - Order Book Imbalance Engine",
            "M09.09 - Microstructure Monitoring Engine",
            "M10.01 - Historical Scenarios Engine",
            "M10.02 - Hypothetical Scenarios Engine",
            "M10.03 - Market Crash Simulation Engine",
            "M10.04 - Sector Shock Simulation Engine",
            "M10.05 - Correlation Shock Engine",
            "M10.06 - Liquidity Stress Testing Engine",
            "M10.07 - Monte Carlo Scenarios Engine",
            "M10.08 - Scenario Comparison Engine",
            "M10.09 - Stress Loss Attribution Engine",
            "M11.01 - Portfolio Risk Limits Engine",
            "M11.02 - Position Limits Engine",
            "M11.03 - Sector Limits Engine",
            "M11.04 - Liquidity Limits Engine",
            "M11.05 - Dynamic Limits Engine",
            "M11.06 - Breach Detection Engine",
            "M11.07 - Breach Classification Engine",
        ],
    }

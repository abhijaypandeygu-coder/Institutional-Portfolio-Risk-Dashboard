"""
M13.09 - Historical Analytics Package Init.
"""

from backend.app.modules.dashboard_visualization.historical_analytics.router import router as historical_analytics_router

__all__ = [
    "historical_analytics_router",
]

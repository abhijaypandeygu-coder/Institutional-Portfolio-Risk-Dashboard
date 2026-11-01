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


@app.get("/health", tags=["System"])
async def root_health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "module": "M01 - Feed Registry & Configuration",
        "modules": [
            "M01 - Feed Registry & Configuration",
            "M02 - Market Data Ingestion Engine",
        ],
    }

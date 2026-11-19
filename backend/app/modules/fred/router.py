"""
FRED (Federal Reserve Economic Data) integration router.
Provides macro-economic indicators for M08 (Factor & Systematic Risk) and M10 (Stress Testing).
"""
import time
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, HTTPException

from backend.app.core.config import settings

router = APIRouter()

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# Series used by M08 (Factor Risk) and M10 (Scenario/Stress Analysis)
FRED_SERIES: Dict[str, str] = {
    "DGS10": "10Y_Treasury",
    "T10Y2Y": "Yield_Spread_10Y2Y",
    "BAMLH0A0HYM2": "High_Yield_Spread",
    "STLFSI4": "Financial_Stress_Index",
}

# Simple in-memory cache: (data, fetched_at)
_cache: Dict[str, Any] = {}
_CACHE_TTL = 300  # 5 minutes


def _fetch_series(series_id: str, api_key: str) -> List[Dict]:
    resp = requests.get(
        FRED_BASE,
        params={"series_id": series_id, "api_key": api_key, "file_type": "json", "limit": 30, "sort_order": "desc"},
        timeout=10,
    )
    resp.raise_for_status()
    observations = resp.json().get("observations", [])
    result = []
    for obs in observations:
        try:
            value = float(obs["value"])
        except (ValueError, TypeError):
            continue
        result.append({"date": obs["date"], "series_id": series_id, "label": FRED_SERIES[series_id], "value": value})
    return result


@router.get("/fred/metrics")
async def get_fred_metrics() -> List[Dict]:
    """Return latest macro-economic metrics from FRED. Results are cached for 5 minutes."""
    api_key = settings.FRED_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="FRED_API_KEY not configured. Set it in your .env file.",
        )

    now = time.time()
    cached = _cache.get("fred_metrics")
    if cached and (now - cached["fetched_at"]) < _CACHE_TTL:
        return cached["data"]

    all_data: List[Dict] = []
    errors: List[str] = []
    for series_id in FRED_SERIES:
        try:
            all_data.extend(_fetch_series(series_id, api_key))
        except Exception as e:
            errors.append(f"{series_id}: {e}")

    if not all_data and errors:
        raise HTTPException(status_code=502, detail=f"FRED fetch failed: {'; '.join(errors)}")

    _cache["fred_metrics"] = {"data": all_data, "fetched_at": now}
    return all_data


@router.get("/fred/latest")
async def get_fred_latest() -> Dict[str, Optional[float]]:
    """Return only the most recent value for each FRED series."""
    data = await get_fred_metrics()
    latest: Dict[str, Optional[float]] = {label: None for label in FRED_SERIES.values()}
    seen: set = set()
    for point in data:
        label = point["label"]
        if label not in seen:
            latest[label] = point["value"]
            seen.add(label)
    return latest

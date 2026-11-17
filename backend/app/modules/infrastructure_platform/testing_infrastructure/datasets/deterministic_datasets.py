import json
import hashlib
from typing import Dict, Any, List


PORTFOLIO_REFERENCE_DATASET_V1: Dict[str, Any] = {
    "dataset_id": "DS_PORTFOLIO_REF_001",
    "name": "Institutional Baseline Portfolio (5 Assets, India & US)",
    "version": "1.0.0",
    "dataset_type": "portfolio",
    "schema_version": "v1",
    "positions": [
        {"symbol": "RELIANCE", "market": "IN", "exchange": "NSE", "quantity": 1000, "price": 2850.50, "market_value": 2850500.0, "currency": "INR", "sector": "Energy"},
        {"symbol": "TCS", "market": "IN", "exchange": "NSE", "quantity": 500, "price": 4120.00, "market_value": 2060000.0, "currency": "INR", "sector": "Technology"},
        {"symbol": "INFY", "market": "IN", "exchange": "NSE", "quantity": -400, "price": 1850.00, "market_value": -740000.0, "currency": "INR", "sector": "Technology"}, # Short
        {"symbol": "AAPL", "market": "US", "exchange": "NASDAQ", "quantity": 200, "price": 225.00, "market_value": 45000.0, "currency": "USD", "sector": "Technology"},
        {"symbol": "MSFT", "market": "US", "exchange": "NASDAQ", "quantity": -100, "price": 420.00, "market_value": -42000.0, "currency": "USD", "sector": "Technology"} # Short
    ],
    "cash_balances": [
        {"currency": "INR", "amount": 1500000.0},
        {"currency": "USD", "amount": 50000.0}
    ]
}

MARKET_RETURNS_DATASET_V1: Dict[str, Any] = {
    "dataset_id": "DS_RETURNS_REF_001",
    "name": "Deterministic 10-Day Market Returns Series",
    "version": "1.0.0",
    "dataset_type": "market_data",
    "schema_version": "v1",
    "returns": [
        0.0125, -0.0084, 0.0210, -0.0150, 0.0035,
        -0.0195, 0.0080, 0.0145, -0.0055, -0.0220
    ],
    "losses": [
        -0.0125, 0.0084, -0.0210, 0.0150, -0.0035,
        0.0195, -0.0080, -0.0145, 0.0055, 0.0220
    ]
}

ORDER_BOOK_SNAPSHOT_V1: Dict[str, Any] = {
    "dataset_id": "DS_ORDERBOOK_REF_001",
    "name": "L2 Order Book Deterministic Snapshot",
    "version": "1.0.0",
    "dataset_type": "order_book",
    "symbol": "RELIANCE",
    "bids": [
        {"price": 2850.0, "quantity": 1500.0},
        {"price": 2849.5, "quantity": 2500.0},
        {"price": 2849.0, "quantity": 4000.0}
    ],
    "asks": [
        {"price": 2850.5, "quantity": 1200.0},
        {"price": 2851.0, "quantity": 3000.0},
        {"price": 2851.5, "quantity": 5000.0}
    ]
}


def get_dataset_checksum(data: Dict[str, Any]) -> str:
    """Computes SHA-256 hash for dataset integrity."""
    serialized = json.dumps(data, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

"""
Module 03.02: Price Validation - Integration Interfaces.
Provides contracts and bridge implementations for:
- M04 Instrument & Reference Data (instrument master, tick sizes, price bands, corporate actions)
- M01 Feed Registry (provider and feed capability resolution)
- M02 Market Data Ingestion (canonical price schemas)
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"
    COMMODITY = "COMMODITY"
    FX = "FX"


class ExchangeVenue(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"


@dataclass
class InstrumentMetadata:
    instrument_id: str
    symbol: str
    exchange: str
    asset_class: AssetClass = AssetClass.EQUITY
    currency: str = "INR"
    tick_size: Decimal = Decimal("0.05")
    price_precision: int = 2
    min_price: Optional[Decimal] = Decimal("0.01")
    max_price: Optional[Decimal] = Decimal("1000000.00")
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExchangePriceBand:
    instrument_id: str
    exchange: str
    effective_date: date
    upper_band: Decimal
    lower_band: Decimal
    band_percentage: Optional[Decimal] = None
    is_official: bool = True
    source: str = "EXCHANGE_FEED"


@dataclass
class CorporateActionAdjustment:
    instrument_id: str
    effective_date: date
    action_type: str  # SPLIT, REVERSE_SPLIT, BONUS, DIVIDEND, RIGHTS
    ratio: Decimal = Decimal("1.0")
    cash_amount: Optional[Decimal] = None
    notes: Optional[str] = None


@dataclass
class ReferencePriceSnapshot:
    instrument_id: str
    exchange: str
    reference_type: str  # PREVIOUS_CLOSE, OFFICIAL_REFERENCE, PRIOR_ACCEPTED, INDEPENDENT_PROVIDER
    reference_value: Decimal
    currency: str = "INR"
    source_provider: str = "EXCHANGE"
    source_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retrieval_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    effective_date: Optional[date] = None
    is_adjusted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class InstrumentReferenceService:
    """
    Bridge service for M04 reference metadata.
    Provides authoritative instrument parameters, exchange price bands,
    corporate actions, and official reference prices.
    When M04 database tables are created in subsequent modules, this adapter
    binds to them without modifying M03.02 validator implementations.
    """

    def __init__(self):
        # Default in-memory instrument catalog for active equities
        self._instruments: Dict[str, InstrumentMetadata] = {
            # Indian Equities (NSE/BSE)
            "RELIANCE": InstrumentMetadata(
                instrument_id="RELIANCE",
                symbol="RELIANCE",
                exchange="NSE",
                currency="INR",
                tick_size=Decimal("0.05"),
                price_precision=2,
                min_price=Decimal("1.00"),
                max_price=Decimal("10000.00"),
            ),
            "INFY": InstrumentMetadata(
                instrument_id="INFY",
                symbol="INFY",
                exchange="NSE",
                currency="INR",
                tick_size=Decimal("0.05"),
                price_precision=2,
                min_price=Decimal("1.00"),
                max_price=Decimal("5000.00"),
            ),
            "TCS": InstrumentMetadata(
                instrument_id="TCS",
                symbol="TCS",
                exchange="NSE",
                currency="INR",
                tick_size=Decimal("0.05"),
                price_precision=2,
                min_price=Decimal("1.00"),
                max_price=Decimal("10000.00"),
            ),
            # US Equities (NYSE/NASDAQ)
            "IBM": InstrumentMetadata(
                instrument_id="IBM",
                symbol="IBM",
                exchange="NYSE",
                currency="USD",
                tick_size=Decimal("0.01"),
                price_precision=2,
                min_price=Decimal("0.01"),
                max_price=Decimal("1000.00"),
            ),
            "AAPL": InstrumentMetadata(
                instrument_id="AAPL",
                symbol="AAPL",
                exchange="NASDAQ",
                currency="USD",
                tick_size=Decimal("0.01"),
                price_precision=2,
                min_price=Decimal("0.01"),
                max_price=Decimal("1000.00"),
            ),
            "MSFT": InstrumentMetadata(
                instrument_id="MSFT",
                symbol="MSFT",
                exchange="NASDAQ",
                currency="USD",
                tick_size=Decimal("0.01"),
                price_precision=2,
                min_price=Decimal("0.01"),
                max_price=Decimal("1000.00"),
            ),
        }

        # Configured price bands (e.g. 10% circuit limits for Indian equities, LULD for US)
        self._price_bands: Dict[str, ExchangePriceBand] = {
            "RELIANCE": ExchangePriceBand(
                instrument_id="RELIANCE",
                exchange="NSE",
                effective_date=date.today(),
                upper_band=Decimal("3300.00"),
                lower_band=Decimal("2700.00"),
                band_percentage=Decimal("10.0"),
            ),
            "INFY": ExchangePriceBand(
                instrument_id="INFY",
                exchange="NSE",
                effective_date=date.today(),
                upper_band=Decimal("1980.00"),
                lower_band=Decimal("1620.00"),
                band_percentage=Decimal("10.0"),
            ),
            "IBM": ExchangePriceBand(
                instrument_id="IBM",
                exchange="NYSE",
                effective_date=date.today(),
                upper_band=Decimal("240.00"),
                lower_band=Decimal("190.00"),
                band_percentage=Decimal("10.0"),
            ),
        }

        # Corporate actions registry
        self._corporate_actions: Dict[str, List[CorporateActionAdjustment]] = {}

        # Reference price snapshots cache
        self._reference_snapshots: Dict[str, Dict[str, ReferencePriceSnapshot]] = {}

    def get_instrument_metadata(self, instrument_id: str) -> Optional[InstrumentMetadata]:
        # Support ticker with or without dot-exchange (e.g., RELIANCE or RELIANCE.BSE)
        clean_id = instrument_id.split(".")[0].upper()
        if clean_id in self._instruments:
            return self._instruments[clean_id]
        if instrument_id.upper() in self._instruments:
            return self._instruments[instrument_id.upper()]
        return None

    def register_instrument(self, metadata: InstrumentMetadata) -> None:
        self._instruments[metadata.instrument_id.upper()] = metadata

    def get_exchange_price_band(
        self, instrument_id: str, exchange: str, check_date: date
    ) -> Optional[ExchangePriceBand]:
        clean_id = instrument_id.split(".")[0].upper()
        band = self._price_bands.get(clean_id)
        if band and band.exchange.upper() == exchange.upper():
            return band
        return None

    def set_exchange_price_band(self, band: ExchangePriceBand) -> None:
        self._price_bands[band.instrument_id.upper()] = band

    def get_corporate_actions(
        self, instrument_id: str, start_date: date, end_date: date
    ) -> List[CorporateActionAdjustment]:
        clean_id = instrument_id.split(".")[0].upper()
        actions = self._corporate_actions.get(clean_id, [])
        return [a for a in actions if start_date <= a.effective_date <= end_date]

    def register_corporate_action(self, action: CorporateActionAdjustment) -> None:
        clean_id = action.instrument_id.split(".")[0].upper()
        if clean_id not in self._corporate_actions:
            self._corporate_actions[clean_id] = []
        self._corporate_actions[clean_id].append(action)

    def get_reference_price(
        self, instrument_id: str, reference_type: str
    ) -> Optional[ReferencePriceSnapshot]:
        clean_id = instrument_id.split(".")[0].upper()
        inst_refs = self._reference_snapshots.get(clean_id, {})
        return inst_refs.get(reference_type)

    def set_reference_price(self, snapshot: ReferencePriceSnapshot) -> None:
        clean_id = snapshot.instrument_id.split(".")[0].upper()
        if clean_id not in self._reference_snapshots:
            self._reference_snapshots[clean_id] = {}
        self._reference_snapshots[clean_id][snapshot.reference_type] = snapshot


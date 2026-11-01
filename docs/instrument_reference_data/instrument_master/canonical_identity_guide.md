# M04.01 Canonical Identity and Listings Guide

## 1. Internal Identity Rules
1. **Never use tickers as Primary Keys:** Symbols change across corporate actions and ticker re-assignments. All database relationships link to `instrument_id` (`INST_xxx`).
2. **Never use ISIN as single Primary Key:** While ISIN is ISO 6166 compliant, instruments may be added prior to formal ISIN issuance (e.g. initial listings or proprietary instruments), or ISINs may undergo re-issuance during restructuring.
3. **Immutability of IDs:** An `instrument_id` is never recycled, deleted, or re-assigned.

---

## 2. Dual Listing and Multi-Market Structure
The dashboard supports multi-market equities across India (NSE, BSE) and the US (NYSE, NASDAQ):
- **Dual Listing:** One canonical instrument can possess both an NSE listing (`RELIANCE`) and a BSE listing (`500325`), or an international depositary receipt listing.
- **Listing Independence:** Delisting or trading halts on BSE do not automatically delist the security on NSE.
- **Primary Listing Governance:** At most one active listing per instrument may carry `is_primary_listing = True`.

---

## 3. Effective-Dated Attribute Versioning
Whenever an identity attribute (such as `canonical_name` or `lifecycle_status`) changes:
- The previous state is archived in `m04_instrument_attribute_history` with `effective_from` and `effective_to` timestamps.
- The `current_version` counter on `m04_instruments` is incremented.
- Downstream backtesting and risk engines can query the exact historical metadata as it existed on any historical date without look-ahead bias.

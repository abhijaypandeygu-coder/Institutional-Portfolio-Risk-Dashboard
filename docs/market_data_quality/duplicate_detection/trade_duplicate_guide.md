# Duplicate Trade Detection & Volume Protection Guide

## 1. Challenge: Discerning Duplicates from Legitimate Market Activity
In institutional equities trading, multiple distinct executions regularly occur at the exact same price and volume within milliseconds (e.g. hitting a large limit order block). Deduplicating simply on `price` and `quantity` would drop valid market volume.

---

## 2. Trade Identification Protocol
`M03.05.01` uses a multi-tier identity resolution strategy:
1. **Exchange Trade ID (`EXCHANGE_TRADE_ID`):** Authoritative identifier assigned by NSE, BSE, NASDAQ, or NYSE.
2. **Provider Trade ID (`PROVIDER_TRADE_ID`):** Assigned by upstream ingestion or matching gateways.
3. **Execution Sequence Number:** Evaluated in conjunction with the connection epoch.
4. **Fallback Composite Fingerprint:** Evaluates high-resolution source timestamp, price, quantity, side, and trade condition simultaneously.

---

## 3. Volume and Turnover Protection
When an incoming trade is classified as a confirmed duplicate (`DUPLICATE_EVENT`):
- The second delivery is assigned to `DuplicateEventReceipt`.
- No row is added to `market_trade_events`.
- Volume ($Q$) and turnover ($P \times Q$) are credited to `prevented_volume` and `prevented_turnover` counters.
- Downstream risk and VWAP calculators receive only the single canonical record.

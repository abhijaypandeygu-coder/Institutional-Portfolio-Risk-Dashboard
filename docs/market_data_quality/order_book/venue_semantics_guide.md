# Venue Semantics Guide: Continuous vs Auction Trading

## 1. Overview
Order book behavior differs between continuous order-driven markets and call auction sessions. This guide details regulatory conventions and execution logic applied by `M03.04`.

---

## 2. Venue Policy Matrix

| Venue | Primary Asset Class | Continuous Cross Allowed | Continuous Lock Allowed | Auction Cross Allowed | Fractional Shares | Min Lot Size |
|---|---|---|---|---|---|---|
| **NSE** | Indian Equities | No (0ms) | No (0ms) | Yes (`AUCTION_CROSS_VALID`) | No | 1.0 |
| **BSE** | Indian Equities | No (0ms) | No (0ms) | Yes (`AUCTION_CROSS_VALID`) | No | 1.0 |
| **NYSE** | US Equities | Yes (transient $\le 50\text{ms}$) | Yes (transient $\le 100\text{ms}$) | Yes (`AUCTION_CROSS_VALID`) | Yes | 1.0 |
| **NASDAQ**| US Equities | Yes (transient $\le 50\text{ms}$) | Yes (transient $\le 100\text{ms}$) | Yes (`AUCTION_CROSS_VALID`) | Yes | 1.0 |
| **SIMULATOR**| Synthetic Multi-asset | Yes ($\le 100\text{ms}$) | Yes ($\le 200\text{ms}$) | Yes (`AUCTION_CROSS_VALID`) | Yes | 1.0 |

---

## 3. Call Auction Dynamics
During call auctions (pre-open, post-close, or volatility auctions):
- Orders accumulate without continuous matching.
- As buy and sell orders enter, the indicative book crosses ($\text{Best Bid} > \text{Best Ask}$) or locks ($\text{Best Bid} == \text{Best Ask}$) around the indicative clearing equilibrium price.
- **Classification:** `AUCTION_CROSS_VALID` and `LOCKED_AUCTION_VALID`.
- **Downstream Gating:** Bid-ask spread calculations are gated (`spread_eligible = False`), but order book imbalance is preserved (`imbalance_eligible = True`).

---

## 4. Continuous Trading Violations
In continuous trading:
- **Crossing:** Best Bid > Best Ask indicates an execution failure or delayed book dissemination. If unresolved beyond transient threshold ($> 50\text{ms}$), it is tagged `CROSSED_CONFIRMED` and raises a `BookIntegrityIncident`.
- **Locking:** Best Bid == Best Ask indicates zero spread. Persistent locks indicate frozen matching engines and are tagged `LOCKED_SUSPICIOUS`.

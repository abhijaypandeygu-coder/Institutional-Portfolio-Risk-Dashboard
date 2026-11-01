# M06.01 Gross Exposure Architecture & Technical Specification

## 1. Executive Overview

**M06.01 — Gross Exposure** represents the foundational market-risk engine of the *Institutional Portfolio Risk Dashboard*. Its core responsibility is the exact quantification of total absolute market commitments across individual portfolios and consolidated portfolio groups before offsetting long and short positions.

In institutional prime brokerage, quantitative hedge funds, and risk oversight units, **gross exposure** is the primary metric indicating aggregate leverage, market footprint, margin utilization, and systemic liquidation risk.

---

## 2. Core Mathematical Specifications

### 2.1 Position Valuation & Conversion
For each eligible position $i \in \mathcal{P}$:
$$\text{Signed Market Value}_i = q_i \times P_i$$
where $q_i$ is the signed quantity from M05.02 ($q_i > 0$ for Long, $q_i < 0$ for Short), and $P_i$ is the authoritative mark price from M05.03.

When converted to reporting currency $C_{\text{rep}}$ with exchange rate $FX_{c \to \text{rep}}$:
$$\text{Converted Market Value}_i = \text{Signed Market Value}_i \times FX_{c \to \text{rep}}$$

### 2.2 Exposure Aggregations (Strict Non-Offsetting)
$$\text{Long Exposure} = \sum_{i \in \text{Long}} |\text{Converted Market Value}_i|$$
$$\text{Short Exposure} = \sum_{i \in \text{Short}} |\text{Converted Market Value}_i|$$
$$\text{Gross Exposure} = \text{Long Exposure} + \text{Short Exposure}$$
$$\text{Net Exposure (Analytical Context)} = \text{Long Exposure} - \text{Short Exposure}$$

*Rule of Invariance:* Under no circumstances may long and short exposures net or offset against each other in the computation of gross exposure. $\text{Gross Exposure} \ge \max(\text{Long Exposure}, \text{Short Exposure})$.

### 2.3 Gross Exposure Ratio
$$\text{Gross Exposure Ratio} = \frac{\text{Gross Exposure}}{\mathcal{D}}$$
$$\text{Gross Exposure Ratio Percentage} = \text{Gross Exposure Ratio} \times 100$$
where $\mathcal{D}$ is the explicitly resolved denominator (NAV, Total Equity, Regulatory Capital, or Committed Capital).

---

## 3. Denominator Handling & Edge Cases

| Scenario | Denominator $\mathcal{D}$ | Calculation Status | Ratio Value | Audit Explanation |
|---|---|---|---|---|
| Normal | $\mathcal{D} > 0$ | `VALID` | $\text{Gross} / \mathcal{D}$ | Normal ratio computed with full precision. |
| Zero Denominator | $\mathcal{D} = 0$ | `INVALID_ZERO_DENOMINATOR` | `None` / `NULL` | Zero denominator prevents mathematical division; marked invalid. |
| Negative Denominator | $\mathcal{D} < 0$ | `INVALID_NEGATIVE_DENOMINATOR` | `None` / `NULL` | Negative capital/NAV yields meaningless leverage ratio; marked invalid. |
| Missing / Stale | Denominator unresolvable | `DENOMINATOR_UNAVAILABLE` | `None` / `NULL` | Required denominator could not be fetched or resolved. |

---

## 4. Multi-Portfolio and Group Aggregation

Integrating with **M05.08 Multi-Portfolio Management**, M06.01 supports calculating group gross exposure across arbitrary portfolio hierarchies:
1. **Deduplication:** Uses `MultiPortfolioService.resolve_group_portfolios` to traverse recursive sub-groups, deduplicating portfolios so double-counting cannot occur.
2. **Lineage Preservation:** Maintains `ExposureContribution` records retaining each position's originating `portfolio_id`, `account_id`, `instrument_id`, and source `snapshot_id`.
3. **Multi-Currency Normalization:** All legs are converted deterministically into the group's requested reporting currency using audited conversion tables.

---

## 5. Audit Trail & Deterministic Manifest

Every exposure run generates an immutable `ExposureCalculationRun` record with an SHA-256 hash `manifest_hash`:
$$\text{manifest\_hash} = \text{SHA256}(\text{run\_id} \parallel \text{portfolio\_or\_group\_id} \parallel \text{gross\_exposure} \parallel \text{long\_exposure} \parallel \text{short\_exposure} \parallel \text{as\_of})$$
This guarantees tamper-evident provenance across regulatory filings and risk disclosures.

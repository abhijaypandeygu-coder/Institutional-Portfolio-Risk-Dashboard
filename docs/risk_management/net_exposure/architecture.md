# M06.02 Net Exposure Architecture & Technical Specification

## 1. Executive Overview

**M06.02 — Net Exposure** provides the directional market-risk quantification engine of the *Institutional Portfolio Risk Dashboard*. While M06.01 Gross Exposure measures the aggregate footprint and leverage without offsetting, **Net Exposure measures the net directional bias** after accounting for the opposing forces of long and short positions.

The engine determines whether a portfolio is:
1. `NET_LONG`: Long Exposure materially exceeds Short Exposure.
2. `NET_SHORT`: Short Exposure materially exceeds Long Exposure.
3. `APPROX_NEUTRAL`: Long and Short Exposures are approximately balanced within configurable absolute or relative tolerance bands.

---

## 2. Core Quantitative Formulations

### 2.1 Signed Market Value & Directional Aggregations
For each eligible position $i$:
$$\text{Signed Market Value}_i = q_i \times P_i$$
where $q_i$ is signed quantity ($q_i > 0$ for Long, $q_i < 0$ for Short) and $P_i$ is the authoritative mark price from M05.03.

When normalized to reporting currency $C_{\text{rep}}$ with exchange rate $FX_{c \to \text{rep}}$:
$$\text{Converted Signed Market Value}_i = \text{Signed Market Value}_i \times FX_{c \to \text{rep}}$$

### 2.2 Exposure Components
$$\text{Long Exposure } (L) = \sum_{i \in \text{Long}} |\text{Converted Signed Market Value}_i|$$
$$\text{Short Exposure } (S) = \sum_{i \in \text{Short}} |\text{Converted Signed Market Value}_i|$$

### 2.3 Net Market Value Formula
$$\boxed{\text{Net Market Value } (N) = L - S \equiv \sum_{i} \text{Converted Signed Market Value}_i}$$
Both formulations strictly reconcile to the exact penny under Python `Decimal` arithmetic.

### 2.4 Net Exposure Ratio
$$\text{Net Exposure Ratio } (R) = \frac{N}{\mathcal{D}}$$
$$\text{Net Exposure Ratio Percentage } (R_{\%}) = \frac{N}{\mathcal{D}} \times 100$$
where $\mathcal{D}$ is an explicitly validated capital denominator (e.g. NAV). Negative ratios are strictly preserved and never clamped to zero.

---

## 3. Neutrality Band & Directional Classification

To avoid unstable noise-driven state flipping when net exposure is near zero, M06.02 supports three configurable threshold styles:

1. **Absolute Neutrality Threshold ($T_{\text{abs}}$):**
   $$|N| \le T_{\text{abs}} \implies \text{APPROX\_NEUTRAL}$$
2. **Relative Neutrality Threshold ($T_{\text{rel}}$):**
   $$\left|\frac{N}{\mathcal{D}}\right| \le T_{\text{rel}} \implies \text{APPROX\_NEUTRAL}$$
3. **Combined Semantics:**
   - `AND`: Both absolute and relative bounds must be satisfied.
   - `OR`: Either absolute or relative bound satisfaction classifies the state as `APPROX_NEUTRAL`.

When outside the neutral band:
- $N > 0 \implies \text{NET\_LONG}$
- $N < 0 \implies \text{NET\_SHORT}$

---

## 4. Currency-Aware Normalization

Direct addition or netting between incompatible currencies (e.g. INR and USD) is strictly forbidden.
- Native signed values are preserved in `NetExposureContribution`.
- Each position is individually converted into the reporting currency using verified FX multipliers before analytical netting.

---

## 5. Multi-Portfolio and Group Aggregation

- Integrates with `MultiPortfolioService.resolve_group_portfolios(group_id, as_of)` from M05.08.
- Strictly deduplicates member portfolios across recursive hierarchies.
- Maintains complete contributor lineage back to originating portfolio, account, instrument, and position snapshot.

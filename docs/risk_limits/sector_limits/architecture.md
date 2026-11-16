# M11.03 — Sector Limits Architecture Document

## 1. Executive Overview

**M11.03 — Sector Limits** establishes configurable, institutional-grade concentration restrictions across sectors and industries, and enforces active overweight and underweight boundaries relative to benchmark indices.

The module provides continuous risk boundary enforcement against excessive single-sector or single-industry concentration, active bets, and unclassified portfolio leakage.

---

## 2. Core Architectural Pillars

### 2.1 Multi-Tier Limit Dimensions
1. **Sector Caps:** Absolute upper bounds as a percentage of NAV or notional value.
2. **Industry Caps:** Granular exposure constraints for sub-sectors and industry groups within a sector.
3. **Benchmark-Relative Active Limits:** Symmetric and asymmetric constraints on active weights ($ActiveWeight = PW_s - BW_s$).
4. **Classification Coverage & Unclassified Tracking:** Explicit identification and accounting of unclassified instruments to prevent silent exposure leakages or renormalization distortions.

### 2.2 Mathematical Model
- **Gross Sector Market Value:**
  $$GrossMV_s = \sum_{i \in s} |MV_i|$$
- **Net Sector Market Value:**
  $$NetMV_s = \sum_{i \in s} MV_i$$
- **Long / Short Exposures:**
  $$LongMV_s = \sum_{i \in s} \max(MV_i, 0), \quad ShortMV_s = \sum_{i \in s} \max(-MV_i, 0)$$
- **Sector Weight (% NAV):**
  $$SectorWeight_s = \frac{GrossMV_s}{NAV_p} \times 100$$
- **Benchmark-Relative Active Weight:**
  $$ActiveWeight_s = PW_s - BW_s$$
  - Overweight breach: $\max(0, ActiveWeight_s - UpperLimit_s)$
  - Underweight breach: $\max(0, LowerLimit_s - ActiveWeight_s)$
- **Classification Coverage:**
  $$Coverage\% = \frac{ClassifiedGrossExposure}{TotalGrossExposure} \times 100$$

---

## 3. Database Schema Overview

The module uses SQLAlchemy 2.0 async models with `Mapped[Optional[T]]` annotations and exact `Numeric(18, 4)` precision:

1. `m11_sector_limit_configurations`: Limit rules defining threshold values, warning thresholds, benchmark references, directionality, and classification targets.
2. `m11_sector_limit_profiles`: Reusable limit profile headers grouping sector rules.
3. `m11_sector_limit_assignments`: Target assignments linking profiles to portfolios or mandates.
4. `m11_sector_limit_evaluations`: Evaluation execution headers recording NAV, coverage metrics, and breach counters.
5. `m11_sector_limit_evaluation_results`: Granular rows recording actual exposure, benchmark weight, active weight, remaining capacity, and status.
6. `m11_sector_limit_breach_events`: Immutable breach logs feeding M11.08 breach escalation.
7. `m11_sector_limit_audit_logs`: Audit trail logging configuration changes and evaluation events.

---

## 4. Integration Boundaries

- **Upstream Modules:**
  - **M04.02 Security Classification Engine:** Source of truth for GICS, ICB, and internal sector/industry mapping hierarchies.
  - **M05.02 Position Management & M05.03 Valuation:** Real-time mark-to-market position exposures and portfolio NAV.
- **Downstream Modules:**
  - **M11.07 Pre-Trade Limits:** Real-time proposed order simulation and compliance verification.
  - **M11.08 Breach Management & Escalation:** Ingestion of structured breach events and notifications.

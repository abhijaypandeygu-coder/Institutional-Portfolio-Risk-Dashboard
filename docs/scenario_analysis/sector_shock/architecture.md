# M10.04 — Sector Shock Simulation Architecture

## 1. Executive Summary

The **M10.04 Sector Shock Simulation** module implements an institutional-grade sector and industry stress-testing framework within the **Institutional Portfolio Risk Dashboard**.

Unlike broad-market crash simulations (M10.03), which model macro index shocks across an entire equity universe, M10.04 isolates concentrated adverse shocks to specific sectors (e.g., Financials, Energy) or industries (e.g., Software, Banks). It models direct group impacts, sensitivity-adjusted security responses ($\beta_{i,s}$), indirect sector-to-sector and sector-to-factor spillovers ($S = W \cdot R_{\text{direct}}$), and multi-channel attribution without double counting.

---

## 2. Core Methodologies & Mathematical Foundations

### 2.1 Direct Sector & Industry Shocks
- **Uniform Group Return:** $R_{i,\text{direct}} = R_{s,\text{shock}}$.
- **Sensitivity-Adjusted Response:** $R_{i,\text{direct}} = \beta_{i,s} \cdot R_{s,\text{shock}}$.
- **Precedence Hierarchy (`MOST_SPECIFIC_WINS`):** Industry shock takes precedence over parent sector shock for constituent holdings unless configured otherwise.

---

### 2.2 Spillover Transmission Engine
Models adverse contagion and cross-sector effects:
1. **Sector-to-Sector Transmission:**
   $$S_i = \sum_{j=1}^N w_{ij} \cdot R_{j,\text{direct}}$$
   where $w_{ij}$ is the configured transmission coefficient from source sector $j$ to target sector $i$.
2. **Sector-to-Factor Transmission:**
   $$F_{k,\text{spillover}} = \sum_{j=1}^N a_{kj} \cdot R_{j,\text{direct}}$$
   $$R_{i,\text{factor}} = \sum_{k=1}^K \beta_{i,k} \cdot F_{k,\text{spillover}}$$
   where $a_{kj}$ maps sector shocks to systematic risk factors and $\beta_{i,k}$ represents the security's factor loadings (from M08.03).

---

### 2.3 Sector Shock Composition & Boundaries
Combines four separate impact channels:
$$R_{i,\text{scenario}} = R_{i,\text{direct}} + R_{i,\text{spillover}} + R_{i,\text{factor}} + R_{i,\text{manual}}$$
Enforces $R_{i,\text{scenario}} \ge -1.0$ (-100% price return boundary).

---

### 2.4 Multi-Currency & Revaluation Engine
- Multi-currency conversion: $(1 + R_{\text{base}}) = (1 + R_{\text{local}})(1 + R_{\text{FX}})$.
- Signed long/short revaluation:
  $$\text{MV}_{i,0} = q_i \cdot P_{i,0}, \quad P_{i,s} = P_{i,0}(1 + R_{i,\text{base}}), \quad \text{MV}_{i,s} = q_i \cdot P_{i,s}$$
  $$\text{PnL}_i = \text{MV}_{i,s} - \text{MV}_{i,0} = q_i \cdot P_{i,0} \cdot R_{i,\text{base}}$$
- Positive loss: $\text{Loss}_i = \max(0, -\text{PnL}_i)$.
- Portfolio NAV & return reconciliation:
  $$\text{PnL}_{\text{portfolio}} = \sum_{i=1}^N \text{PnL}_i, \quad \text{NAV}_s = \text{NAV}_0 + \text{PnL}_{\text{portfolio}}, \quad R_{\text{portfolio}} = \frac{\text{PnL}_{\text{portfolio}}}{\text{NAV}_0}$$
  $$C_i = \frac{\text{PnL}_i}{\text{NAV}_0}, \quad \sum_{i=1}^N C_i \equiv R_{\text{portfolio}}$$

---

### 2.5 Multi-Channel Loss Attribution
Decomposes portfolio PnL across four independent channels:
$$\text{PnL}_{\text{total}} = \text{PnL}_{\text{direct}} + \text{PnL}_{\text{spillover}} + \text{PnL}_{\text{factor}} + \text{PnL}_{\text{manual}}$$
Provides hierarchical sector and industry aggregation without double counting parent-child losses.

---

## 3. Database Architecture

13 normalized relational models under SQLAlchemy 2.x:
1. `SectorShockScenario`: Header metadata, ownership, category, and versioning.
2. `SectorShockScenarioVersion`: Immutable configuration snapshot with SHA-256 fingerprint.
3. `SectorShockGroupDefinition`: Direct sector/industry shock definitions and methods.
4. `SectorShockMembershipSnapshot`: Point-in-time frozen classification mapping of holdings.
5. `SectorSpilloverRelationship`: Source-to-target spillover links (sector-to-sector and sector-to-factor).
6. `SectorSpilloverRelationshipVersion`: Immutable versions of spillover relationship definitions.
7. `SectorShockMappingResult`: Per-run resolved instrument mappings.
8. `SectorShockSimulationRun`: Execution master record with NAV, PnL, loss, and coverage metrics.
9. `SectorShockPositionResult`: Detailed position revaluation outputs.
10. `SectorShockGroupResult`: Aggregated sector and industry group performance.
11. `SectorShockAttributionResult`: Channel and group decomposition records.
12. `SectorShockWarning`: Diagnostic warnings and caveats.
13. `SectorShockAuditLog`: Lifecycle and execution audit trail.

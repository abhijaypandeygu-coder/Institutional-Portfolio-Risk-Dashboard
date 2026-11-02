# M08.01 — Factor Definition: Architecture & Engineering Guide

## 1. Overview & Conceptual Foundation

**M08.01 — Factor Definition** serves as the foundational registry and quantitative specification layer for **M08 — Factor & Systematic Risk Analytics** within the **Institutional Portfolio Risk Dashboard**.

In modern quantitative portfolio management and multi-factor risk modeling, factors must never be treated as ad-hoc time-series or ephemeral labels. Instead, an equity factor is an analytically explicit, economically motivated systematic driver of asset returns whose definition, characteristic formulas, breakpoints, portfolio weighting rules, and universe constraints are rigorously specified, version-controlled, and immutable.

### Canonical Factor Universe

M08.01 formalizes and registers the standard multi-factor asset pricing canon across both Indian (NSE/BSE, INR) and US (NYSE/NASDAQ, USD) markets:

1. **Market Factor ($MKT$):** Captures broad market equity risk premium ($R_m - R_f$) over the risk-free cash benchmark.
2. **Size Factor ($SMB$ — Small Minus Big):** Captures the return differential between small-capitalization and large-capitalization equities using free-float market capitalization.
3. **Value Factor ($HML$ — High Minus Low):** Captures the valuation premium using Book-to-Market ($B/M$) ratio computed with an explicit 60-day lag to eliminate look-ahead bias.
4. **Momentum Factor ($MOM$ / $WML$ — Winners Minus Losers):** Captures 12-month return persistence skipping the most recent 1-month reversal window ($t-12$ to $t-2$).
5. **Quality Factor ($QMJ$ — Quality Minus Junk):** Multi-attribute composite factor capturing profitability (ROE, Operating Margin), financial leverage (Debt/Equity), and earnings stability (Cash Flow / Assets).

---

## 2. Key Architecture Components

```
+--------------------------------------------------------------------------------------------------+
|                                    M08.01 FACTOR DEFINITION                                      |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   +------------------------------------+          +------------------------------------------+   |
|   |   Factor Registry Identity         |          |   Deterministic Recipe Normalizer        |   |
|   |   - factor_id (UUID)               |          |   - compute_deterministic_hash()         |   |
|   |   - factor_code (e.g. SMB_INDIA)   |          |   - Canonical Factor Specifications      |   |
|   |   - factor_family, factor_type     |          |   - Invariant JSON canonicalization      |   |
|   +-----------------+------------------+          +--------------------+---------------------+   |
|                     |                                                  |                         |
|                     v                                                  v                         |
|   +-----------------+--------------------------------------------------+---------------------+   |
|   |   Factor Definition Version (Immutable)                                                  |   |
|   |   - version_id (UUID), version_number (1, 2, ...)                                        |   |
|   |   - definition_hash (SHA-256)                                                            |   |
|   |   - construction_specification (break points, legs, lookbacks, universe)                 |   |
|   |   - governance_status (DRAFT -> PENDING_REVIEW -> APPROVED -> ACTIVE -> DEPRECATED)      |   |
|   +-----------------+------------------------------------------------------------------------+   |
|                     |                                                                            |
|                     +---------------------------------------+                                    |
|                     |                                       |                                    |
|                     v                                       v                                    |
|   +-----------------+--------------------+   +--------------+--------------------------------+   |
|   |   Deconstructed Characteristics      |   |   Factor Model Builder (e.g., FF3, Carhart4)  |   |
|   |   - characteristic_code (ROE, D/E)   |   |   - model_code, model_version_id              |   |
|   |   - formula_specification            |   |   - model_definition_hash (Ordered SHA-256)   |   |
|   |   - direction, standardization       |   |   - Pinned factor versions (k = 1, ..., K)    |   |
|   |   - winsorization & weight           |   |   - Deterministic factor ordering             |   |
|   +--------------------------------------+   +-----------------------------------------------+   |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 3. Cryptographic Immutability & Hash Lineage

Every factor version possesses a cryptographic `definition_hash` generated via SHA-256 over a deterministically ordered, canonical JSON payload of the factor's construction specification:

$$\text{definition\_hash} = \text{SHA256}(\text{json\_canonical}(\text{spec}))$$

The canonical serializer normalizes dictionary keys, formats floats to fixed precision, converts decimal numbers, and normalizes nested lists. If an analyst modifies a parameter (e.g., changes lookback from 252 days to 126 days, or alters a breakpoint from 30% to 20%), the engine enforces the creation of a new version ($v+1$) with a distinct `definition_hash`. Prior versions remain immutable to guarantee full quantitative reproducibility.

---

## 4. Governance Lifecycle State Machine

Factor definitions and factor models adhere to institutional risk committee governance:

```
[ DRAFT ] 
    |
    v (Action: SUBMIT)
[ PENDING_REVIEW ] 
    |
    +---> (Action: REJECT) ---------> [ REJECTED ]
    |
    v (Action: APPROVE)
[ APPROVED ] 
    |
    v (Action: ACTIVATE)
[ ACTIVE ] 
    |
    v (Action: DEPRECATE)
[ DEPRECATED ]
```

---

## 5. Downstream Integration Contracts

M08.01 establishes the foundational data contracts for subsequent M08 modules:
- **M08.02 (Factor Returns):** Computes time series of daily returns strictly consuming approved/active `FactorDefinitionVersion` contracts.
- **M08.03 (Factor Exposures):** Computes security-level factor loadings ($\beta_{i,k}$) referencing exact pinned factor characteristics and definitions.
- **M08.04 (Systematic vs. Idiosyncratic Risk):** Decomposes portfolio risk variance based on `FactorModelVersion` covariance matrices.

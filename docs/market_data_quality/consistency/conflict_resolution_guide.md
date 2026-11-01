# Source Precedence & Conflict Resolution Guide

## 1. Automated vs. Manual Resolution Framework
When two eligible feeds disagree on the price of an equity beyond the configured tolerance threshold, a `ConsistencyConflict` is raised.

The engine resolves conflicts via two explicit pathways:

### Pathway A: Automated Source Precedence
- Rules defined in `m03_source_precedence_rules` assign priorities ($1, 2, 3\dots$, where $1$ is highest precedence) by exchange, market, provider, and observation type.
- If Source A has Priority 1 and Source B has Priority 2, the conflict is automatically resolved:
  - `conflict_status = "AUTO_RESOLVED"`
  - `selected_source = Source A`
  - `resolution_method = "SOURCE_PRECEDENCE"`
- Both raw observations remain untouched in the database; the resolved view establishes canonical downstream data.

### Pathway B: Manual Operator Review
- If sources have equal priority or no precedence rule exists, the conflict enters `PENDING_MANUAL_REVIEW`.
- Authorized operators submit a resolution via `POST /api/v1/quality/consistency/conflicts/{key}/resolve` selecting `ACCEPT_SOURCE_A`, `ACCEPT_SOURCE_B`, or `REJECT_BOTH` with mandatory text justification.
- An immutable entry is written to `m03_consistency_resolution_history` for compliance and auditability.

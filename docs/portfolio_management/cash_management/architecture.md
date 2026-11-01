# Architecture Specification: M05.04 Cash Management

## 1. Domain Overview
`M05.04 Cash Management` is the authoritative cash accounting subledger and cash availability calculation engine of the Institutional Portfolio Risk Dashboard. It manages:
- Multi-currency cash accounts by portfolio and account (INR, USD).
- Balanced double-entry financial journals (debit increases cash asset, credit decreases cash asset).
- Settled cash tracking via immutable cash movements.
- Earmarked cash reservations across the commitment lifecycle (orders, trades, fees).
- Restricted cash holds (pledged collateral, regulatory locks).
- Explainable available cash calculation with double-counting prevention.
- Same-currency internal transfers and FX-backed cross-currency transfers.
- External statement reconciliation.

---

## 2. Mathematical Formulation

### 2.1 Conservative Available Cash Formula
$$\text{Available Cash} = \text{Settled Cash} + \text{Eligible Receivables} + \text{Eligible Credit} - \text{Active Reservations} - \text{Restricted Cash} - \text{Minimum Cash Buffer} - \text{Unreserved Payables}$$

Where:
- **Eligible Receivables**: Default $0$ unless permitted by portfolio policy.
- **Eligible Credit**: Approved credit facility limit if permitted by policy.
- **Active Reservations**: $\sum \text{remaining\_amount}$ across `ACTIVE` and `PARTIALLY_RELEASED` reservations.
- **Restricted Cash**: $\sum \text{restricted\_amount}$ across active holds.
- **Minimum Cash Buffer**: Configured mandatory safety buffer.
- **Unreserved Payables**: Payables lacking an active reservation (preventing double counting).

---

## 3. Double-Counting Prevention
When an executed trade settles:
1. The cash movement debit is posted to the settled cash subledger.
2. The corresponding reservation is atomically converted to `SETTLED` (`remaining_amount = 0`).
3. The underlying commitment status is marked `SETTLED`.
This ensures that the obligation does not reduce available cash twice.

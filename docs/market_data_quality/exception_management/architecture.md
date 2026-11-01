# M03.08 Exception Management Architecture

## 1. Overview
The **M03.08 — Exception Management Engine** provides institutional-grade remediation, quarantine, rejection, controlled correction, and idempotent replay capabilities for market data observations across the Institutional Portfolio Risk Dashboard.

It strictly adheres to the core financial data integrity axiom:
> **No invalid or suspect observation may silently enter the trusted market-data path. No original observation may be silently overwritten or deleted.**

```mermaid
flowchart TD
    subgraph Upstream Detection (M03.01 - M03.07)
        Findings["Validation Findings (Price, Time, Book, Consistency)"]
    end

    subgraph M03.08 Intake & Registration
        Intake["Intake & Correlation Engine\nDeterministic Key Generation"]
        ExcRecord["Exception Record\n(Lifecycle State: OPEN -> IN_REVIEW -> ...)"]
    end

    subgraph Controlled Isolation
        QRN["Quarantine Isolation\n(M02 Notification, Payload Hash Preserved)"]
        REJ["Rejection Registry\n(Structured Reason Codes, Recoverability)"]
    end

    subgraph Remediation & Governance
        Notes["Investigation Notes & Evidence"]
        Proposal["Correction Proposal\n(Before & After Values, Precision Preserved)"]
        Approval["Approval Workflow\n(Separation of Duties Enforced)"]
    end

    subgraph Replay & Resolution
        ReplayReq["Idempotent Replay Request\n(M02 Ingestion Execution)"]
        M02Pipeline["M02 Ingestion Pipeline & M03 Validation"]
        Resolution["Resolution Audit Event\n(Audit Trail & Downstream Release)"]
    end

    Findings --> Intake
    Intake --> ExcRecord
    ExcRecord --> QRN
    ExcRecord --> REJ
    ExcRecord --> Notes
    QRN --> Proposal
    Proposal --> Approval
    Approval --> ReplayReq
    ReplayReq --> M02Pipeline
    M02Pipeline --> Resolution
```

## 2. Separation of State Machine
M03.08 strictly separates **Workflow Status** (operational triage of the incident case) from **Record Disposition** (the physical eligibility and isolation state of the underlying observation):

- **Workflow Statuses:** `OPEN`, `TRIAGED`, `IN_REVIEW`, `AWAITING_INFORMATION`, `CORRECTION_PENDING`, `AWAITING_APPROVAL`, `APPROVED`, `REPLAY_PENDING`, `REPLAYING`, `RESOLVED`, `DISMISSED`, `REOPENED`.
- **Record Dispositions:** `TRUSTED`, `QUARANTINED`, `REJECTED`, `CORRECTION_PENDING`, `READY_FOR_REPLAY`, `REPLAYING`, `REPLAYED`, `REPLAY_FAILED`, `RELEASE_PENDING`, `RELEASED`.

## 3. Strict Safety and Data Governance Controls
1. **Separation of Duties:** The user or service who creates a correction proposal is strictly forbidden from approving it. Approval requires independent authorized review (`supervisor` / `admin`).
2. **Provenance Guard:** Synthetic market simulator data is prevented from being used as authoritative evidence to correct real provider observations.
3. **Payload Immutability:** Payloads are hashed (SHA-256) upon arrival and stored in tamper-evident snapshot records; original records in M02 are never overwritten.
4. **Idempotent Replay:** Replays use deterministic keys derived from observation ID, correction version, and operation scope to prevent duplicate trade prints or double-counting in downstream VaR engines.


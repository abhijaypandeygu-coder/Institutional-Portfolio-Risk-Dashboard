# Architecture: M04.07 — Instrument Mapping

## 1. Executive Summary
The **Instrument Mapping Engine (M04.07)** provides canonical resolution services connecting external identifiers from exchanges, data vendors (e.g. Bloomberg, Refinitiv), brokers, and internal platform services to authoritative canonical internal entities (`instrument_id` and `listing_id` defined in M04.01).

External identifiers can never be used as primary canonical keys within the platform. The mapping engine guarantees deterministic resolution, fail-closed ambiguity handling, namespace-specific normalization, bitemporal validity lookups, and pre-ingestion validation contracts.

---

## 2. Core Components

```
                   Incoming Feed / User Request
           (raw_identifier, namespace_code, exchange_mic)
                                |
                                v
               +----------------------------------+
               |     Identifier Normalizer        |
               | - Whitespace trimming            |
               | - Case normalization             |
               | - Leading zero preservation      |
               | - Suffix stripping (.US, .NS)    |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |        Resolution Engine         |
               | - Candidate query by date/feed   |
               | - Exact verified match           |
               | - Multi-venue disambiguation     |
               +----------------------------------+
                     /                      \
            (Single Match)           (Multiple / None)
                  /                            \
                 v                              v
      +----------------------+       +-------------------------+
      | Resolved Canonical   |       | Conflict / Rejection    |
      | Instrument & Listing |       | - AMBIGUOUS_MATCH       |
      | is_eligible = True   |       | - Conflict Logged       |
      +----------------------+       | is_eligible = False     |
                                     +-------------------------+
```

### 2.1 Namespace Registry (`identifier_namespaces`)
- Maintains distinct identifier namespaces (`EXCHANGE_SYMBOL`, `EXCHANGE_SECURITY_CODE`, `VENDOR_SYMBOL`, `BROKER_SECURITY_ID`, `ISIN`, `SEDOL`, `CUSIP`, `RIC`).
- Configures normalization rules per namespace (`case_sensitive`, `strip_suffix`, `provider_name`, `exchange_code`).

### 2.2 External Identifier Mappings (`external_identifier_mappings`)
- Bitemporally versioned relationships between normalized external codes and internal canonical keys (`instrument_id` referencing `m04_instruments`, and `listing_id`).
- Governed by statuses: `APPROVED_FOR_INGESTION`, `PENDING_REVIEW`, `DEPRECATED`, `REJECTED`, and verification statuses (`VERIFIED`, `UNVERIFIED`).

### 2.3 Ambiguity & Conflict Recording (`mapping_conflict_records`)
- Enforces strict institutional fail-closed semantics: when a ticker or code maps to multiple canonical targets without sufficient context (e.g. missing exchange MIC), resolution returns `AMBIGUOUS_MATCH`, rejects ingestion eligibility (`is_eligible_for_ingestion = False`), and logs a structured conflict record for administrative resolution.


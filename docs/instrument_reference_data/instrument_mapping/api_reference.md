# API Reference: M04.07 — Instrument Mapping

## Base Path: `/api/v1/instrument-mappings`

### 1. Register Identifier Namespace
- **POST** `/namespaces`
- **Request Body:**
```json
{
  "namespace_code": "BLOOMBERG_TICKER",
  "namespace_name": "Bloomberg Composite Ticker",
  "namespace_type": "VENDOR_SYMBOL",
  "provider_name": "BLOOMBERG",
  "exchange_code": "XNAS",
  "case_sensitive": false,
  "strip_suffix": true
}
```
- **Response:** `201 Created`

### 2. List Identifier Namespaces
- **GET** `/namespaces`
- **Response:** `200 OK` (Array of `IdentifierNamespaceResponse`)

### 3. Create External Identifier Mapping
- **POST** `/`
- **Request Body:**
```json
{
  "mapping_id": "MAP_001",
  "namespace_code": "BLOOMBERG_TICKER",
  "external_identifier_raw": "AAPL.US",
  "target_type": "LISTING_LEVEL",
  "instrument_id": "INST_AAPL_123",
  "listing_id": "LIST_AAPL_XNAS",
  "exchange_code": "XNAS",
  "mapping_status": "APPROVED_FOR_INGESTION",
  "effective_from": "2020-01-01",
  "source_reference": "BLOOMBERG_FEED"
}
```
- **Response:** `201 Created`

### 4. Resolve Identifier
- **POST** `/resolve`
- **Request Body:**
```json
{
  "namespace_code": "BLOOMBERG_TICKER",
  "raw_identifier": "aapl.us",
  "as_of_date": "2024-01-15",
  "exchange_code": "XNAS"
}
```
- **Response:** `200 OK`
```json
{
  "matching_level": "EXACT_VERIFIED_MATCH",
  "raw_identifier": "aapl.us",
  "normalized_identifier": "AAPL",
  "namespace_code": "BLOOMBERG_TICKER",
  "instrument_id": "INST_AAPL_123",
  "listing_id": "LIST_AAPL_XNAS",
  "exchange_code": "XNAS",
  "mapping_id": "MAP_001",
  "mapping_version": 1,
  "is_eligible_for_ingestion": true,
  "candidate_instrument_ids": [],
  "reason": null
}
```

### 5. Bulk Resolution
- **POST** `/resolve/bulk`
- **Request Body:**
```json
{
  "requests": [
    {
      "namespace_code": "BLOOMBERG_TICKER",
      "raw_identifier": "AAPL.US",
      "exchange_code": "XNAS"
    },
    {
      "namespace_code": "BLOOMBERG_TICKER",
      "raw_identifier": "UNKNOWN"
    }
  ]
}
```
- **Response:** `200 OK` (`total_requested`, `resolved_count`, `unresolved_count`, `results`)


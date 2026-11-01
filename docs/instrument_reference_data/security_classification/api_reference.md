# M04.02 Security Classification API Reference

All endpoints are hosted under `/api/v1/classifications`.

## 1. Scheme & Taxonomy Endpoints

### Register Classification Scheme
- **POST** `/api/v1/classifications/schemes`
- **Headers:** `X-API-Key: admin_dev_secret_key_2026`
- **Body:**
```json
{
  "scheme_code": "GICS_2024",
  "scheme_name": "Global Industry Classification Standard 2024",
  "description": "Standard four-tiered hierarchical classification taxonomy",
  "provider": "MSCI / S&P",
  "scheme_type": "EXTERNAL_STANDARD",
  "applicable_market_scope": "GLOBAL",
  "is_primary_default": true
}
```

### Create Taxonomy Node
- **POST** `/api/v1/classifications/schemes/{scheme_code}/versions/{version_code}/nodes`
- **Headers:** `X-API-Key: admin_dev_secret_key_2026`
- **Body (Sector):**
```json
{
  "node_code": "45",
  "node_name": "Information Technology",
  "node_description": "Hardware, software, and semiconductor technology firms",
  "node_type": "SECTOR",
  "hierarchy_level": 1
}
```
- **Body (Industry):**
```json
{
  "node_code": "4510",
  "node_name": "Software",
  "node_description": "Software products, cloud infrastructure, and services",
  "node_type": "INDUSTRY",
  "parent_node_id": "NOD_45_SECTOR_ID",
  "hierarchy_level": 2
}
```

---

## 2. Instrument Classification Endpoints

### Assign Instrument Classification
- **POST** `/api/v1/classifications/instruments/{instrument_id}/assignments`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "scheme_code": "GICS_2024",
  "sector_code": "45",
  "industry_code": "4510",
  "valid_from": "2026-01-01T00:00:00Z",
  "assignment_source": "OFFICIAL_ISSUER",
  "assignment_reason": "Primary revenue derived from enterprise software"
}
```

### Assign Asset Category
- **POST** `/api/v1/classifications/instruments/{instrument_id}/asset-category`
- **Headers:** `X-API-Key: operator_dev_secret_key_2026`
- **Body:**
```json
{
  "category_code": "COMMON_EQUITY",
  "assignment_source": "M04_01_INHERITED",
  "assignment_reason": "Ordinary voting equity shares"
}
```

### Lookup Point-In-Time Classification
- **GET** `/api/v1/classifications/instruments/{instrument_id}?scheme_code=GICS_2024&as_of_valid_time=2026-03-01T00:00:00Z`
- **Headers:** `X-API-Key: readonly_dev_secret_key_2026`

---

## 3. High-Performance Bulk Retrieval (Portfolio & Risk Consumers)

### Bulk Lookup
- **POST** `/api/v1/classifications/bulk-lookup`
- **Headers:** `X-API-Key: readonly_dev_secret_key_2026`
- **Body:**
```json
{
  "instrument_ids": [
    "INST_AAPL_UUID",
    "INST_MSFT_UUID",
    "INST_RELIANCE_UUID"
  ],
  "scheme_code": "GICS_2024",
  "as_of_valid_time": "2026-06-01T00:00:00Z"
}
```

### Coverage Metrics
- **GET** `/api/v1/classifications/metrics/coverage`
- **Headers:** `X-API-Key: readonly_dev_secret_key_2026`

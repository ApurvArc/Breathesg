# Data Model Design

## Overview

BreatheESG uses a **three-tier ingestion architecture** that mirrors financial accounting principles:

```
Upload → RawIngestionLog → StagingRecord → CarbonLedger
```

---

## Tier 1: RawIngestionLog (Immutable receipt)

Every file uploaded creates exactly one `RawIngestionLog`. The SHA-256 hash of the raw file bytes serves as a cryptographic deduplication key — uploading the same utility bill twice is rejected at this layer before any rows are parsed.

```
RawIngestionLog
 id: UUIDv4 (prevents enumeration)
 tenant: FK → Tenant (strict multi-tenancy)
 file_sha256: SHA-256 of raw bytes (dedup key)
 source_type: SAP | UTILITY | TRAVEL
 detected_encoding: UTF-8, CP1252, etc.
 detected_delimiter: , or ;
 status: PROCESSING → DONE | FAILED | DUPLICATE
 total_rows / parsed_rows / error_rows / flagged_rows
 is_locked: bool (set by analyst before sending to auditor)
```

---

## Tier 2: StagingRecord (Mutable analyst workspace)

One `StagingRecord` per parsed row. Analysts interact exclusively here via the React dashboard. The `raw_json` field stores the verbatim original CSV row — analysts can always see the exact source data.

Status transitions form a **strict state machine**:

```
PENDING → APPROVED → [committed to CarbonLedger]
         ↘ FLAGGED → APPROVED | REJECTED
         ↘ REJECTED → PENDING (reopen)
```

Key fields:
- `raw_json`: verbatim original row, never modified
- `normalized_quantity / normalized_unit`: after unit conversion (Wh→kWh, Gallons→Litres, MT→KG)
- `co2e_kg / co2_kg / ch4_kg / n2o_kg`: GHG breakdown
- `parse_warnings`: array of machine-readable flags (e.g. `suspicious_date:future`, `material_unclassified`)
- `emission_factor`: FK to EmissionFactor (versioned)

---

## Tier 3: CarbonLedger (Append-only)

Receives exactly one entry when an analyst approves a `StagingRecord`. **Cannot be edited in place.** Corrections require a reversal entry (negative `co2e_metric_tons`) followed by a new corrected entry — mirroring double-entry financial accounting.

The `emission_factor_snapshot` JSON column captures the exact factor values at time of approval, so future annual factor updates (DEFRA publishes new factors every June) never silently alter historical inventories.

```
CarbonLedger
 id: UUIDv4
 tenant / facility
 staging_record: OneToOne FK (full chain of custody)
 scope: 1 | 2 | 3
 category: FUEL_COMBUSTION | ELECTRICITY | BUSINESS_TRAVEL_*
 emission_factor: FK (frozen at approval time)
 emission_factor_snapshot: JSON (exact values, immutable)
 co2e_metric_tons / co2 / ch4 / n2o
 is_reversal: bool
 approved_by / approved_at
```

---

## Supporting Tables

### Tenant & Multi-tenancy
All data is scoped by `tenant_id`. UUID primary keys prevent cross-tenant enumeration attacks. The `CurrentUserMiddleware` / `TenantUser` model enforces that API endpoints only return data for the authenticated user's tenant.

### EmissionFactor
Versioned lookup table seeded from DEFRA 2025 and EPA eGRID 2025. Keyed by `(category, source, publication_year, geographic_scope)`. The FK is embedded in `StagingRecord` and snapshotted in `CarbonLedger`.

### Facility
Geographic resolution model. Maps SAP plant codes to physical locations. The `grid_region_code` field drives eGRID subregion lookup for US facilities (e.g. CAMX = California). UK facilities use the DEFRA national grid factor.

### AuditLog
Written by Django `post_save` signals via thread-local user capture. Every `StagingRecord` status transition, every analyst correction, every batch lock generates an immutable audit entry. The `before_json` / `after_json` columns record exact field-level diffs.

# Trade-offs & Intentional Omissions

This document explains what was explicitly **not** built, and why.

---

## 1. Spend-based Scope 3 calculation (not built)

**What it is:** For purchased goods without activity data (e.g. SAP materials that can't be classified by fuel type), the GHG Protocol recommends using spend × spend-based emission factor ($/£ × kgCO2e/$).

**Why omitted:** Spend-based factors have ±300-500% uncertainty and are considered a last resort. They require EEIO (Environmentally Extended Input-Output) databases like USEEIO or Exiobase, which are large (>1GB), require significant preprocessing, and have complex sector mappings. For a 4-day prototype, it's better to flag unclassified materials clearly than produce numbers with false precision. The architecture supports adding this as a Scope 3 Category 1 pipeline.

---

## 2. Market-based Scope 2 calculations (not built)

**What it is:** Market-based Scope 2 uses supplier-specific emission factors from energy attribute certificates (RECs, GOs, PPAs) rather than the grid average.

**Why omitted:** Requires integration with certificate registries (REGO in UK, M-RETS in US), supplier disclosure documents, and complex certificate retirement tracking. The location-based method we implement is correct and is always required even when market-based is also reported (dual reporting per GHG Protocol Scope 2 Guidance).

---

## 3. Task queue / async processing (not built)

**What it is:** Celery + Redis/RabbitMQ for background file processing.

**Why omitted:** For files up to 50MB with well-written Python parsers, synchronous processing completes in <30 seconds. A task queue adds significant operational complexity (separate worker process, broker config, monitoring). For a prototype, synchronous is correct. The Django view runs the parser in-request and returns only after processing completes, so the UI always shows the result immediately.

**When to add it:** When files exceed ~10,000 rows or when multiple concurrent uploads from the same tenant become common.

---

## 4. Scope 3 Category 11 (Use of sold products) and Category 15 (Investments)

**Why omitted:** These categories require product lifecycle assessments and portfolio-level financial data that have nothing to do with the operational data ingestion pipeline described in the brief (fuel, electricity, travel). They are Scope 3 categories that would require entirely different data sources.

---

## 5. Real-time stream ingestion / webhooks

**What it is:** Instead of file uploads, pull data directly from SAP via RFC APIs, from utility portals via Green Button Connect (OAuth), or from Concur via its REST API.

**Why omitted:** Each of these integrations requires client-specific authentication setup (SAP RFC credentials, utility portal OAuth2 registration, Concur OAuth). The brief explicitly called for ingesting file exports, which is the current reality for most enterprise clients. The architecture (with `source_type` and parser dispatch) is designed to add real-time connectors later.

---

## 6. Statistical anomaly detection

**What it is:** Flag records whose values are statistical outliers vs historical data from the same facility/material/period.

**Why a simplified version:** We implemented simple heuristics (zero quantity, >1M units, future dates). True statistical anomaly detection (e.g. z-score vs 12-month rolling baseline) requires sufficient historical data — which doesn't exist in a prototype. The architecture is designed to extend: the `parse_warnings` array and `FLAGGED` status form the correct hook.

---

## 7. Scope 3 Category 3 T&D losses as separate ledger entries

**Why omitted for now:** UK transmission and distribution losses (0.0183 kgCO2e/kWh per DEFRA 2024) are computed and stored in the utility parser output but not written as separate `CarbonLedger` entries in this prototype. In production, T&D losses would be a separate Scope 3 Category 3 line item in the ledger with a clear label distinguishing it from the Scope 2 market/location-based figure.

---

## 8. Radiative Forcing for all flights (partial)

**Decision taken:** We include RF by default for all DEFRA 2025 aviation factors (the values already embed RF). Some clients prefer RF-excluded figures for specific regulatory filings. A production system would store both and let the client choose per-report.

---

## 9. Currency conversion for spend-based Scope 3

**Why omitted:** The architecture captures the source currency from SAP (EUR, GBP, USD) but does not implement FX conversion. For activity-based calculations (fuel, electricity, travel distance), currency is irrelevant — we use quantity not spend. For future spend-based Scope 3, an FX API integration would be needed.

---

## Summary Priority Matrix

| Feature | Complexity | Prototype Value | Status |
|---------|-----------|----------------|--------|
| SAP fuel combustion parsing | High | High |  Built |
| Utility calendarization | Medium | High |  Built |
| Travel IATA/Haversine | Medium | High |  Built |
| Audit trail (signals) | Medium | High |  Built |
| Analyst review queue | Medium | High |  Built |
| Append-only ledger | Medium | High |  Built |
| Spend-based Scope 3 | Very High | Medium |  Omitted |
| Market-based Scope 2 | High | Medium |  Omitted |
| Async task queue | Medium | Low |  Omitted |
| API connectors (SAP RFC) | Very High | Low |  Omitted |

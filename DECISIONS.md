# Design Decisions & Ambiguity Resolution

## 1. Which emission factor source to use?

**Decision: DEFRA 2025 primary, EPA eGRID 2025 for US electricity**

**Reasoning:** The brief mentioned a UK-centric enterprise client (Breathe ESG is a UK company). DEFRA/DESNZ publishes the most comprehensive and granularly updated UK emission factors annually. For US electricity, eGRID is the authoritative source with subregion-level granularity (29 subregions vs one national figure). IPCC AR6 GWPs are embedded in the DEFRA factors for CH4 and N2O.

**The 100-year vs 20-year GWP question:** Used 100-year GWPs (IPCC AR6) per GHG Protocol standard. The 20-year GWP would give a 3-4x higher methane factor — a significant divergence worth flagging to the client if they're reporting under SEC rules where some guidance suggests 20-year.

---

## 2. How to handle SAP movement type reversals?

**Decision: Sign-preserve, don't filter, flag if 262 not paired with 261**

The SAP reversal movement types (262 cancels 261, 202 cancels 201) should result in **negative emissions entries** in the staging record. This is the correct approach because:
- Net emissions should be computed at the aggregate (ledger) level, not filtered out
- Auditors can trace exactly which document was reversed
- A 262 without a corresponding 261 is a data quality issue that analysts should review

The parser automatically negates quantities for reversal movement types. The analyst sees both the original and reversal in the staging table and can verify the net is correct.

---

## 3. Billing period vs. calendar month alignment for electricity

**Decision: Linear daily-rate calendarization with explicit flag**

When a utility bill covers 2023-12-18 to 2024-01-15 (crossing a month boundary), the energy is prorated across those calendar months using a linear daily rate:

```
daily_rate = total_kWh / billing_days
Dec allocation = daily_rate × 14 days
Jan allocation = daily_rate × 15 days
```

This is the most defensible, explainable methodology for auditors. The alternative (allocating to the month of bill end date) is simpler but harder to justify if the billing period spans a significant portion of two months. Each calendarized sub-period is flagged with `is_calendarized=True` and both the original billing period and split periods are visible to analysts.

---

## 4. Which Scope for each data type?

| Source | Scope | GHG Protocol Category |
|--------|-------|----------------------|
| SAP fuel combustion (diesel, petrol, natural gas) | 1 | Stationary/mobile combustion |
| SAP electricity purchases | 2 | Purchased electricity |
| Utility electricity (Scope 2 location-based) | 2 | Market-based requires supplier-specific EF |
| Utility T&D losses | 3 | Category 3: Energy-related activities |
| Business travel flights | 3 | Category 6: Business travel |
| Business travel hotels | 3 | Category 6: Business travel |
| Business travel ground | 3 | Category 6: Business travel |
| SAP purchased goods (unclassified materials) | 3 | Category 1: Purchased goods & services |

**The Scope 2 location-based vs market-based ambiguity:** We use location-based (grid average factor) because we have no supplier-specific contracts data. A real implementation would need to integrate renewable energy certificates (RECs/GOs) for market-based reporting.

---

## 5. What flight distance calculation method?

**Decision: Haversine great-circle distance + 8% DEFRA routing uplift**

The 8% uplift is DEFRA-mandated to account for the fact that aircraft don't fly exactly great-circle routes (air traffic control, weather diversions, etc.). This is built into the UK government's own carbon calculator methodology.

We considered using actual flight route databases (OAG, FlightStats) but these require paid APIs. For a 4-day prototype, Haversine + uplift is accurate to within ±5% and is explicitly what DEFRA recommends for Scope 3 Category 6 calculations.

---

## 6. What to do with unclassified SAP materials?

**Decision: Classify as Scope 3 / Purchased Goods, flag for analyst review**

SAP material codes (MATNR) are client-specific — there's no universal mapping from material codes to emission categories. We use keyword matching on the material description text (MAKTX) to classify obvious fuel materials. Everything else goes to "Purchased Goods" with a `material_unclassified` warning.

In production, this would use a client-specific mapping table that the sustainability team maintains. The flagging mechanism ensures analysts review these before approval.

---

## 7. Duplicate detection

**Decision: SHA-256 of raw file bytes, checked per tenant**

Uploading the same utility bill twice is the most common cause of double-counting in carbon inventories. We hash the raw file bytes (not the parsed content) so any modification — even a metadata change — produces a different hash. The check is scoped per tenant so the same file can be uploaded by different clients.

---

## 8. Emission factor versioning

**Decision: FK + JSON snapshot at approval time**

The `EmissionFactor` table is FK-linked from `StagingRecord`. When an analyst approves a record, the exact emission factor values are **snapshotted into a JSON column** on `CarbonLedger`. This means:
- DEFRA updating their 2024 factors in June 2025 does not retroactively change any approved records
- Auditors can see exactly which factor was used for each entry
- Historical inventory comparisons are stable

This mirrors financial accounting treatment of commodity prices in long-term contracts.

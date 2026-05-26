# Real-World Format Research Sources

## SAP MB51 Export

**Primary research:**
- SAP Help Portal (help.sap.com): MB51 transaction documentation — confirms BUDAT (Buchungsdatum) as posting date field, MATNR as 18-char zero-padded material number, BWART as movement type code
- SAP Community (answers.sap.com): Threads on ALV export delimiters confirming that German locale uses semicolons with decimal commas vs US locale comma with decimal points
- Movement type codes (201/261/262/202): Confirmed via SAP MM documentation — 201 = consumption from WM, 261 = goods issue for order, 262/202 = respective reversals
- Unit of measure codes: SAP internal UoM codes (LT=litre, KG=kilogram, TO=metric ton, M3=cubic metre, KWH=kilowatt-hour) from SAP UoM table T006

**Key finding for prototype:**
SAP exports the session language as metadata — German installations export `Buchungsdatum` where US installations export `Posting Date`. Both must be mapped to the same canonical field. Our column alias table covers ~30 known aliases.

**Date format trap:** SAP's internal BUDAT format is YYYYMMDD but the ALV GUI export renders it as the user's date format preference (DD.MM.YYYY for German users, MM/DD/YYYY for US). Both appear in the same client's files depending on who ran the export.

---

## Utility Electricity Data

**Primary research:**
- Green Button Alliance (greenbuttonalliance.org): Official specification for Green Button CSV format — confirms TYPE/DATE/START DATE/END DATE/USAGE/UNITS/COST/NOTES headers
- Octopus Energy API documentation (developer.octopus.energy): Half-hourly export format — `Consumption (kWh)`, `Start`, `End` columns; ISO 8601 timestamps
- ENERGY STAR Portfolio Manager (energystar.gov): ESPM upload template — `Start Date`, `End Date`, `Quantity`, `Units`, `Meter Name` columns; monthly billing periods
- UK smart meter data formats: BEIS Smart Meter Implementation Programme documentation confirms that UK SMETS2 meters can export in Wh (not kWh) — source of common 1000x errors

**Key finding for prototype:**
The Wh vs kWh distinction is the most dangerous unit discrepancy in utility data. UK Hildebrand Glow and similar HAN devices export in `consumption_wh`. If not caught, 8,420 kWh becomes 8,420 Wh = 8.42 kWh — a 1000x undercount. Our parser detects this by column name pattern matching.

---

## Corporate Travel Data (Concur)

**Primary research:**
- Concur Developer Center (developer.concur.com): Expense Report export schema documentation — lists standard expense type codes (AIRFR, HOTEL, CARRT, TAXCB, TRAIN)
- DEFRA/DESNZ 2025 GHG Conversion Factors (gov.uk/government/publications): 
  - Business travel: aviation (with/without RF), hotel stays, car types, taxis, rail
  - Aviation factors include separate short-haul/long-haul × cabin class breakdown
  - Short-haul defined as <3,700 km great-circle distance
- ICAO Carbon Emissions Calculator documentation: Confirms 8% routing uplift methodology now also used by DEFRA

**Key finding for prototype:**
Concur does not provide flight distance or CO2e in the standard export. It provides origin/destination city names or airport codes. The mapping to distance requires:
1. IATA code resolution (from city name, often ambiguous — "Paris" could be CDG or ORY)
2. Haversine calculation on lat/lon pairs
3. DEFRA 8% routing uplift

Our airports database covers ~110 major commercial airports with lat/lon. A production system would use the full OurAirports dataset (~15,000 airports).

**Hotel emission factors:**
DEFRA 2025 provides per-country hotel factors. We cover 15 countries. For uncovered countries, we use the global average (12.0 kgCO2e/room-night). The Maldives (MV) outlier at 152.0 kgCO2e/room-night reflects diesel generator dependency on remote islands — this is a real factor that surprises clients.

---

## Emission Factor Primary Sources

| Factor | Source | Year | URL |
|--------|--------|------|-----|
| UK grid electricity | DEFRA/DESNZ GHG Conversion Factors | 2025 | gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2024 |
| Aviation (with RF) | DEFRA/DESNZ GHG Conversion Factors | 2025 | Same |
| Hotels by country | Cornell Hotel Sustainability Benchmarking + DEFRA | 2025 | Same |
| Ground transport | DEFRA/DESNZ GHG Conversion Factors | 2025 | Same |
| Fuel combustion | DEFRA/DESNZ GHG Conversion Factors | 2025 | Same |
| US electricity by subregion | EPA eGRID | 2025 (2023 data) | epa.gov/egrid |

**DEFRA 2025 publication date:** June 2025. The factors embedded in `emissions/factors.py` are the 2025 values. The 2025 publication includes AR6 GWPs for CH4 (27.9, 20-yr: 82.5) and N2O (273, 20-yr: 273).

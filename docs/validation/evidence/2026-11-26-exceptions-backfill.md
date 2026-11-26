# Production Exceptions historical backfill — 2026-11-26

## Request and boundary

The owner requested at least 2026 year-to-date and ideally all of 2025 for
investigating Swiss product codes observed in foreign markets. Initial production
coverage: `2026-07-01 → 2026-11-26 05:35 UTC · 148/148 complete UTC days`, with
6,519 unique source Alerts. This is a purpose-specific historical investigation,
not approval of indefinite detailed-source retention or a QMS release.

The deployed application remains `8e9748d11e149b6d6fd5bbaa7e4acd94a084aa2e`,
schema 0054. No application deployment, credentials, privileges, feature gates,
Hub status/closure or retention settings were changed. The local API Access
increment is still undeployed.

## Execution

Use the existing authenticated production runtime configuration and native
`enqueue(..., 'exceptions', kind='backfill', start=..., end=...)` control. Source
calls use the existing acquisition, page retention, completeness validation,
source-identity deduplication and atomic publication path. Query windows are at
most 30 days; a 31-day month becomes two source queries.

Manual requests 18–24 selected June/January 2026, January 2025 and February–May
2026. June supplied 185 additional Alerts; January 2026 supplied 3,033; January
2025 supplied 57. Thus 2025 access is demonstrated by actual returned records,
not merely acceptance of an empty query.

The existing two-hour scheduled handler then discovered gaps back to the newly
published earliest period and filled the remaining 2025/2026 intervals in bounded
30-day chunks. No parallel second importer or extra 2025 queue was required.
Already queued overlapping monthly requests reuse source Alert identities. The
normal enabled state and two-hour cadence remain unchanged.

## Verified result

Verified at `2026-11-26 07:48:32 UTC`:

| Check | Result |
| --- | --- |
| Coverage | 2025-01-01 → 2026-11-26 07:43 UTC |
| Complete UTC days | 694 / 694; independently checked, zero missing days |
| Source Alerts in 2025 | 5,644 |
| Source Alerts in 2026 year-to-date | 16,591 |
| Total unique source Alerts | 22,235 |
| Additional Alerts | 15,716 |
| Original pre-backfill Alerts retained | All 6,519 |
| Duplicate source-qualified Alert IDs | 0 |
| 2025/2026 Exceptions view rendering | HTTP 200 for each, with all work statuses |
| Installed source hashes | All 393 match the existing deployed manifest |
| Normal schedule | Enabled, 7,200 seconds; next normal run 09:44:02 UTC |

The current UTC day is partial. Accepted query-window coverage does not establish
coverage of every technical error level or every successful scan. The API's
absolute earliest retention boundary is not declared by these results: retrieval
was proved through the requested 2025-01-01 boundary, not tested indefinitely
further backwards. All seven manually requested chunks (18–24) completed successfully on their
first attempt, including the overlapping monthly refreshes; no requests remain
pending for this operation.
Private detailed request/progress/verification evidence is retained in
`tmp/exceptions-backfill-2026-11-26` (not committed source payloads).

The UI supports up to 367 days per Exceptions query: inspect 2025 and 2026
separately. Select **All** work statuses for analytical totals; the default Open
view can omit resolved cases. Source history is not synchronised into development
by this operation.

## Product/market interpretation and additional reports

The provided Exception API Swagger defines `sourceMarket` as the requesting
market. Incoming `National System Intermarket` observations often have an unset
`isIntermarket` flag; do not require that flag to be true. Conversely, CH calls
can have it set when they initiate a request abroad. EU/OBP source events are not
foreign end-user scan evidence. Last pack update market is a different context.

For product analysis, join normalised source GTINs to the selected published SAI
reference. Swiss product/MAH names come exclusively from SAI. Missing/ambiguous
matches remain unresolved; neither a GTIN prefix nor no SAI match establishes
market nationality, pack authenticity or physical export. Retired/historical
Swiss products may need the corresponding historical reference. Counts are
Alerts, not distinct packs, sales or all scans. The aggregate sanity check used
foreign requesting markets and `National System Intermarket`, separately from
source events initiated locally or by OBPs. Detailed business results remain in
private evidence rather than Git.

The production Reporting API catalogue and report definitions were read directly:

| Report | Use | Limit |
| --- | --- | --- |
| Exceptions Audit Trail Report | Additional exception audit points by period; definition supports `businessProcessFilterIMTFulfilment` and `syntheticMonitoring=false` | Not a list of all successful scans; current Alert API does not claim full L3/L4 coverage |
| User Activity Report, IMT Fulfilment | Transaction/exception totals by remote requesting market and day, including IMT verification and state changes; definition supports `imtMarket` | No GTIN/product dimension; currently imported only from 2026-08-01 through 2026-11-25; older activity needs a separate backfill |
| Pack Audit Trail Report | Audit history of a known product code/scheme/serial; includes locally recorded IMT context | Pack-specific, not enumeration of all products scanned abroad |
| Pack Disclosure Stakeholder Report | Pack audit points located through an Alert ID/UPRC | Requires that code; not a complete success-only scan inventory |

System Access Audit Trail supports actor/client/IP and business-process filters;
it is useful for access attribution but is not established here as a complete
product-level IMT transaction report. Snapshots/API Access and pack-state metrics
also do not establish every foreign scan. In the catalogue available to these
credentials, no general period-wide product/GTIN-level report of all successful
IMT fulfilments was identified. Confirm a corresponding export/report with
Solidsoft for a complete successful-scan product list; do not infer it from the
country-level activity aggregate or from the exception-only subset.

## Product analysis sanity check

A separate read-only aggregation found 33 distinct source GTINs with one exact
match to the selected SAI reference, in 34 GTIN/requesting-market pairs across
12 foreign markets (18,159 source Alerts). One additional product/market pair
remains unresolved against SAI. The criterion was source authority + requesting
market outside the local CH/LI market and EU OBP context + `National System
Intermarket`, not a true Intermarket flag. SAI mapping run 11 uses the published
2026-10-05 export. Historical reference coverage and physical pack provenance
are not inferred from that current reference. No client, location, serial or
row-level source payloads are copied into this Git record.

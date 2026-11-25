# Snapshot expiry reconciliation — 2026-11-18

Read-only verification of the local development dataset. This is supporting
technical evidence, not formal business approval or a statement about a separately
refreshed server dataset. No source values, mappings or presentation rules changed.

## Source and scope

- Published Snapshot date: **2026-11-10**; Mapping run **3**.
- Resolved Daily Snapshot processing run: **77**; retained artifact **208**,
  content **190**, original CSV length **10,099,928 bytes**.
- Original artifact length and SHA-256 match the stored integrity metadata.
- Published observed Batch records: **50,584**.

## Independent comparison

Read the Batches section directly from the retained original UTF-8 CSV with the
standard CSV reader. Compare the complete multiset of Product Code Scheme,
Product Code, Batch Id, Product Version Number and Batch Expiry Date against
the current published Batch records and their stored expiry text.

- Original Batches: **50,584**; published Batches: **50,584**.
- Exact source-to-published multiset equality: **true**.
- Changed/missing source rows: **0**; unexpected published rows: **0**.
- Stored expiry versus retained Batch evidence differences: **0**.
- Staging rows available: **50,584**; stored expiry versus staging differences: **0**.

## Format and presentation

All source expiry values contain six digits; there are **1,030** distinct values.
Examples include `270531`, `260531`, `210900` and `000100`. In **492** rows, the
last two digits are `00`; none has `00` in the month position. These are retained
source values, not introduced by parsing, numeric conversion or Excel export.

The six-digit structure is consistent with the GS1 AI (17) YYMMDD notation
([GS1 AI reference](https://ref.gs1.org/ai/)). This comparison does not assign a
century or substitute calendar days for `00`. Any additional ISO/calendar-date
column needs an explicit interpretation rule, including these cases, while
preserving the source value separately.

Code review confirms that the CSV parser keeps strings without date parsing;
Batch mapping copies `Batch Expiry Date` into `expiry_source_text`; catalogue
queries/templates render that source text directly. The field is registered as
text for view conditions/export. An in-memory Excel export/reload of `270531`,
`210900` and `000100` preserves all characters with string cell type and `@`
text format. Existing mapping and portal regressions also cover unresolved raw
expiry values rather than assuming a valid ISO date.

## Creation/expiry plausibility follow-up

Compare all 50,584 observed Batch creation dates with YYMMDD expiry values.
For this analysis only, resolve the two-digit year in a 49-year-past/50-year-future
window around the reference year and interpret day `00` as month end. This is
not a new stored date or a change to import rules. All rows were parseable under
these assumptions; exactly one expiry precedes Batch Creation Date:

| Attribute | Retained source value |
| --- | --- |
| Batch | SCB2CH |
| Product Code | 07612345000206 |
| Product Name · original NMVS source | Scanner Check Product |
| Batch Expiry Date | 000100 |
| Batch Creation Date | 2022-04-14T15:44:37.700Z |
| Product Creation Date | 2022-04-14T15:43:36.450Z |
| Batch State | Expired |
| Packs / Active Packs | 1 / 0 |

The source name suggests a scanner-check/test record; that is an inference, not
a newly verified product classification. Do not generalise this outlier to a
Snapshot-format error or reject it without understanding the source purpose.
The Snapshot's Creation Date must not be equated with a manufacturing date
without a verified field definition.

For the specifically queried expiry `200929`, there is one matching Batch:
`F19184-01`, Product Code `03663502000465`. The original retained CSV supplies
Batch Creation Date `2020-04-09T15:11:56.353Z`, expiry `200929`, state Expired.
Under YYMMDD this is expiry 2020-09-29, after that creation date. The matching
local original record does not have a 2022 creation date.

# User interface language

SMVS Operations uses English for all application-owned user interface text.
Use British English consistently (organisation, fulfilment, authorisation).
This includes navigation, headings, controls, accessibility labels, validation
errors, empty states, background task status messages and generated audit summaries.
Use unambiguous ISO dates (`YYYY-MM-DD`) for application-rendered dates and
explicitly label UTC times. Native date inputs may follow the browser locale.

Preserve original source data exactly as supplied. Do not translate product names,
SAI descriptions, organisation names, API messages, report fields or retained
source evidence. German or French text in these source values is intentional.
Swiss product names and marketing authorisation holders must continue to come
exclusively from SAI; changing the UI language must not change data selection.

Keep tests for application text in English. Test fixtures may contain German or
French source values to verify that original evidence is preserved.

# Portal UI design

Follow the [portal UI conventions](docs/technical/PORTAL-UI-GUIDELINES.md)
when adding or changing portal pages. Use a trailing `→` for contextual links
to related records, evidence or workflows, and a leading `←` for back links.

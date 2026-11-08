# CRM named views and field catalogue

Recorded 2026-11-08. Personal named views, column ordering and the field catalogue
are implemented. Live outstanding-response views and shared views remain planned.

## User-facing behaviour

A named view is a working list, such as **MAHs without an agreement** or
**Outstanding self-declarations**. It stores a name, filter conditions, displayed
columns, their order and sorting. A user can create several views for one directory,
switch between them and choose a personal default. Use **Save view** and
**Save as new view** to distinguish updates from creation. Start with personal
views. Shared views require an explicit scope and editing permissions in a later step.

Replace the current **My filters** field-visibility controls with a view selector
and an explicit **Conditions** editor. Keep quick search available. Preserve
existing column and filter preferences when migrating to the first personal view.

## Example views and their meaning

| Directory | View | Conditions |
| --- | --- | --- |
| MAHs | No agreement | Current directory and no linked agreement |
| MAHs | No signed agreement | Current directory and no linked agreement with status Signed |
| MAHs | Ready for self-declaration | Current directory, a linked Signed agreement and eligible for invoicing |
| Contacts | Alert contacts | Current directory and an alert-management function or assignment, with these two sources distinguished |
| Self-declarations | Outstanding responses | Selected data/invoice year and a request awaiting a response, once the live workflow states are available |

An archived directory is a scope, not an extra condition to infer from record text.
“No agreement” and “No signed agreement” remain separate, matching the existing
queries. Do not infer an outstanding response solely from historical imported
invoice status. Historical self-declarations and current draft/approval/send/receipt
workflow records need an explicit lifecycle mapping. Invitation delivery and the
live receipt workflow are still pending implementation.

## Field catalogue

The original picker exposed only the fields already rendered in each list.
The catalogue now adds maintained business fields, derived relationships and
explicitly labelled source-only values. The inventory below lists
source headers, not a claim that each header is already a maintained CRM field.

For each selectable business field, define a stable key, label, type, current-value
source, display formatter, permitted operators and relationship semantics. Both
column selection and view conditions should use this catalogue. Use maintained
CRM values for editable fields and current relationships for assignments. Identify
retained source-only fields explicitly. Preserve source header text in the import
review. Avoid duplicate columns for legacy Airtable lookups and current relations.
Technical record IDs stay in import review. Bearer credentials such as Auth Code
are excluded from general-purpose list/view fields.

Implement typed conditions with a validated field/operator/value representation.
Start with AND conditions and operators appropriate to the type, including equal,
contains, empty/not empty, any of and numeric/date ranges. Expand OR groups when
needed. Lists, counts, pagination, detail navigation and future exports must use
the same server-side condition semantics. Saved views must respect portal access
and per-record scope. Hidden columns are a display choice.

## Retained source inventory

The counts are from the latest staged export available on 2026-11-08. The initial
selectable columns and quick-filter inputs are shown for comparison.

| Directory | Source headers | Initial selectable columns | Initial quick filters |
| --- | ---: | ---: | ---: |
| MAH | 44 | 5 | 3 |
| Contacts | 12 | 2 | 2 |
| End Users | 20 | 3 | 3 |
| IT Suppliers | 28 | 4 | 1 |
| MAH Agreements | 22 | 5 | 4 |
| Self-declarations | 12 | 5 | 4 |

### MAH

`Record Id`, `MAH Name`, `Parent Company`, `Marketing Authorization in Switzerland`, `Domain`, `Created Time`, `Street`, `City`, `Postal Code`, `Billing country`, `Additional address information`, `Phone`, `GLN`, `UID`, `Signing Date (from Contract)`, `Purchase Order Number`, `Email invoice`, `Email general`, `Eligible for invoicing`, `Checked`, `VAT Number`, `One-time fee charged`, `Alert contacts`, `Status`, `Discount to be applied`, `Tasks`, `Company Size`, `Industry`, `Headquarters Location`, `Contacts`, `SPOC`, `Selfdeclarations`, `Association`, `Logo`, `Invoices`, `Company summary`, `Agreements`, `Contract Status (from Agreements)`, `Last modified time`, `Payment Platform`, `Payment Platform URL`, `Modified Time`, `RECORD_ID`, `Email Payment Inquiries`.

### Contacts

`Record Id`, `First Name`, `Last Name`, `Email`, `Function`, `Link End Users`, `Link IT Supplier`, `Mailbox Type`, `Phone`, `Link MAH`, `Communications`, `RECORD_ID2`.

### End Users

`Record Id`, `End User Name`, `Organisation type`, `SPOC`, `Phone`, `Street`, `City`, `Postal code`, `Country`, `Domain`, `GLN`, `UID`, `Email general`, `Enduser Software Supplier`, `Authorisation Checked`, `Alert contacts`, `Logo`, `Authorisation Number`, `Status`, `Software Product`.

### IT Suppliers

`Record Id`, `IT Supplier Name`, `Status`, `Phone`, `Domain`, `Created Time`, `Modified Time`, `Street`, `City`, `Postal code`, `Country`, `Additional address information`, `GLN`, `UID`, `Email general`, `Qualified`, `End User Software`, `Tasks`, `Company Size`, `Industry`, `Headquarters Location`, `Contacts`, `SPOC`, `Logo URL`, `Logo`, `Company summary`, `Account name (normalized)`, `Target Group`.

### MAH Agreements

`Contract ID`, `Contractor`, `Start Date`, `Status`, `Agreement`, `Type`, `Signing Date`, `Minimum Term (Years)`, `Minimum Term End Date`, `Termination Notice (Months)`, `Auto-Renewal`, `Created By`, `Created Time`, `Last Modified`, `Next Possible Termination Date`, `Counterparty`, `Notes`, `Tasks`, `MAH`, `End Users`, `Affiliates`, `Termination Date`.

### Self-declarations

`Record Id`, `Declaration year`, `RX packs sold`, `Quantity related amount`, `Invoice number`, `RX sales group`, `Sales related amount`, `RX quantity group`, `Base fee code`, `Status`, `Base fee amount`, `MAH Name`.

## Implementation sequence

1. Complete column-order persistence and preserve existing visibility settings.
2. Build the field catalogue, beginning with MAHs and Contacts, then the other CRM directories. Include email, phone, address, status and current relationships where available.
3. Add named personal views and typed conditions using the catalogue. Provide MAHs without an agreement and MAHs without a Signed agreement as starting examples.
4. Add the outstanding self-declaration view once its lifecycle mapping is defined. Include the data year and invoice year explicitly.
5. Add shared views with separate edit permissions when required.


## Implemented field-catalogue behaviour

`app/portal/crm_field_catalogue.py` defines stable keys, labels, types, provenance
and future operator choices for all six directories. The preference API publishes
this metadata. Existing columns remain selected by default. The additional columns
are opt-in, searchable within **My columns**, and support the same personal
visibility and ordering preferences. Old saved orders are extended with newly
available fields without moving the existing columns.

Values use maintained profiles before source defaults, including explicitly
cleared values. Agreement status and signing dates are read from the current
linked agreements. Source-only values carry **imported** in the column name and
retain their original text. Their operator type remains text until a maintained
numeric/date representation is introduced. Source IDs, the normalised supplier
identity formula, duplicate contract lookup fields and temporary attachment URLs
are represented by the current identities/relations or PDF archive instead of
additional source columns. General-purpose secret fields are excluded.

Current assignments and retained import relations are distinct. In Contacts,
**Assigned MAHs** and **Assigned End Users** describe current SPOC/alert-contact
assignments. **Link MAH · imported**, **Link End Users · imported** and
**Link IT Supplier · imported** retain the exported organisation references.

The quick-filter controls remain available. **My filters** is replaced by the
named-view selector and editor. The catalogue supplies the condition operators,
server-side validation and raw values for evaluation.


## Implemented named-view behaviour

Migration `0039_crm_list_views` creates private, versioned records and converts
each previous preference row into a default **My view**, retaining quick-filter
values, column selection and order. Saving locks the owning user row to serialize
creation/default changes and checks the view version. Only the owner and matching
directory may read or change a view. Names are unique per owner/directory.

The controller offers MAH templates for no agreement, no Signed agreement, and
a Signed agreement plus direct-invoicing eligibility. Typed AND conditions and
sorting use the shared raw catalogue values. The complete existing CRM candidate
query is evaluated on the server before pagination. CRM datasets are currently
small, so this evaluation runs in memory. The unmodified SQL pagination path is
retained when no additional conditions or sorting are requested. Field values,
counts, ordering, pages and detail neighbours share the evaluation functions.

Explicit query parameters override saved values. Unsaved condition/sort/column
previews travel with list and detail links. Long previews can be saved as a view
to use a short ID-based URL. Scope parameters such as a parent MAH are retained.
Defaults, quick-filter values and view IDs remain independent of the source data.

The CRM Self-declarations directory currently lists historical imported records.
A view for live outstanding replies needs the planned link to the
invitation/dispatch/receipt lifecycle, rather than a guess from invoice status.
Shared views and OR condition groups remain future work.

## Toolbox presentation

The shared CRM list controller presents a compact View/search toolbar and a
right-hand toolbox with Conditions, Columns and Save view tabs. At 1400 CSS
pixels and above the toolbox shares the results panel with the table; below
that it is a modal overlay with Escape/Close, backdrop, focus containment and
inert background. Apply validates and previews without saving. Session storage
restores the active tab only for the next controller-initiated navigation; no
preference or database schema changes are required. Existing saved views use
the same API and stable field keys.

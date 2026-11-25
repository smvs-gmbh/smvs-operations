# SMVS Operations User Guide

Open this guide using **?** in the portal header. This guide describes the current
CRM review tools and self-declaration preparation workflow. Application controls
are in English; imported names, messages and evidence retain their source language.

## Portal layout and text size

Module tabs appear above the page title. Catalogue tabs switch between **Overview**,
**Products** and **Batches**. Participant tabs switch between **Organisations**, **Locations**
and **Activity**. Detail-view tabs, such as **Root cause analysis** or **Original
data & evidence**, also appear above the title. Filters and data remain below it.

Lists and detail cards use the same text hierarchy across the portal: data values
are more prominent than button labels, while section headings stay compact.
Dashboard figures retain their larger size. Use **A−** and **A+** in the header
to scale the interface, including data and controls, together.

## Catalogue Overview

Open **Catalogue → Overview** for counts from the published Daily Snapshot.
Products with reported packs have a reported pack count above zero. Reported
packs are summed from the Products dataset. The batch count includes all
reported states, including expired batches.

**Serialisation by Swiss MAH** groups SAI-matched products by the SAI holder.
Agreement status comes from the linked CRM agreements and requires exactly one
non-archived CRM match by GLN. **Unassigned** indicates that the link could not
be established. **No signed agreement** indicates that the linked record has
no agreement marked Signed.

## Alert Trends

Open **Exceptions → Alert Trends** for monthly alert counts, grouped by alert
type, and the top five organisations and products in the selected period.
Use **Show A2 and A3** to focus the chart. Open a month or ranking row to see
its alerts in Exceptions, including resolved alerts.

The report counts retained alerts using the source alert date in UTC. A month
marked * contains days without full query coverage. The End User country
filter uses the linked CRM country, including its imported value where applicable.
The requesting market is a separate field. Product names come from SAI.

## Navigate and review CRM records

Open **CRM** and choose **MAHs**, **Agreements**, **Self-declarations**, **Contacts**,
**End Users**, **IT Suppliers** or **Import review**. Open a record by clicking its
name or identifier. Related-record links end with **→**.

On a detail page, the navigation above the title provides **← List**,
**← Previous** and **Next →**. Previous/Next follows the originating list's view,
filters and order, including across pages. It stops at the first or last record.
Use the back link to return to that list.

Read a card without entering edit mode. Where available, choose **Edit** on a
section, then **Save changes** or **Cancel** for that section. Previous/Next
remains visible but disabled while editing or saving, and is enabled again
when all open section edits are saved or cancelled. Renaming a record can change
its position in the list.

### Keyboard shortcuts

Use these shortcuts without scrolling back to the record navigation. On Mac,
**Alt** means **Option (⌥)**. **Shortcuts** in the navigation opens a reference.

| Action | Shortcut |
| --- | --- |
| Next record | Alt + Shift + → |
| Previous record | Alt + Shift + ← |
| Next CRM tab | Alt + Shift + ↓ |
| Back to the originating list | Alt + Shift + ↑ |

Next CRM tab opens the next CRM directory and wraps after the last tab. It does
not move to another record of the same type. On a list page, the record and back
shortcuts have no destination; the tab shortcut remains available.

Shortcuts are paused in input fields, during section editing or saving, with
unsaved record-form changes, and while a toolbox or dialog is open. Save or
cancel editing and close the toolbox first. At a list boundary, Next/Previous
does not wrap to the other end of the list.

## Configure personal CRM views

A view saves a working list for your account and CRM directory: filters,
conditions, columns, column order and sorting. Other users keep their own views.

1. Choose a saved view under **View**, or start with **All records**. MAHs also
   offer **No agreement**, **No signed agreement** and **Ready for self-declaration**
   templates. Templates can be saved as personal views.
2. Use the search field for a quick search. MAHs support **Name or GLN**. Open
   **Configure view** for additional criteria in the right-hand **View toolbox**.
3. In **Conditions**, choose the directory scope and relationship filters where
   offered. Use **Add condition** to select a field, operator and value. All
   conditions must match (AND). Empty/not-empty conditions do not need a value.
   Dates use UTC calendar dates. Choose a sort field and direction as needed.
4. In **Columns**, use **Find a column** to select fields and the **↑/↓** buttons
   to arrange them. The record-link column stays selected. Column changes preview
   immediately. Fields labelled **imported** contain retained Airtable values;
   other profile fields and agreement lookups use the current CRM values.
5. Choose **Apply** to preview the current configuration without overwriting
   the saved view. Counts, pagination and detail Previous/Next navigation follow
   the complete filtered list.
6. In **Save view**, enter a **View name** and choose **Save view**. Use **Save as
   new view** with another name to keep the existing view. Tick **Use as my default
   for this directory** before saving to open the view automatically from the menu.

**Unsaved changes** indicates pending view changes. Closing the toolbox keeps
changes on the current page; save the view to retain them for future visits.
The toolbox stays open on the selected tab after Apply or Save. On wide screens
it sits beside the table; on smaller screens it overlays the page. Use **Close**
or Escape to dismiss it.

**Reset columns** previews the compact standard selection and order. Save the
view to keep that layout. **Delete view** removes the selected personal view after
confirmation. An editor opened before the same view was changed elsewhere must
reload before saving. Specific links retain their requested view and filters.

Earlier personal filter and column preferences are carried into **My view** as
the initial default. The former **My filters** configuration is replaced by views.

## Create a contact

Open **CRM → Contacts** and choose **New contact** beside the title. Enter the
name, function and communication details, then select **Create contact**. At least
a name or email address is required; a shared mailbox can use its email address
without a personal name. Select **Cancel** to return without creating a record.

The new contact can be edited or archived like an imported contact. Assign it
from a MAH or End User's Contacts section using the contact chooser.

## Use record actions

On MAH, Contact and End User detail pages, choose **Actions** beside Previous/Next
to open the right-hand toolbox. It contains archive/restore actions and, for
eligible MAHs, the transfer form. It starts closed. Use **Close** or Escape to
return to the record. On wide screens it sits beside the details; on smaller
screens it overlays them. Finish section editing before using record actions.

### Archive or restore a contact

Open **CRM → Contacts**, open the contact, then choose **Actions → Archive contact**.
In the list, use **Configure view → Conditions → Directory** to find **Archived
contacts**. Open an archived record and choose **Actions → Restore contact** to
return it to the current directory.

Existing assignments remain visible with an archived label. Select an active
contact for new assignments. Archiving is reversible and retains personal data;
it does not permanently delete a contact.

### Transfer a marketing authorisation holder

Use this workflow to record a transfer between two existing MAH records.

1. Open the source MAH under **CRM → MAHs**.
2. Choose **Actions** in the record navigation to open the toolbox.
3. Under **Transfer to**, select the receiving MAH.
4. Review **Agreements to mark as Transferred**. Signed agreements linked only to
   the source MAH are selected by default. Shared agreements start unchecked.
   Selecting a shared agreement changes its status for every linked MAH. Leave it
   unchecked if it should continue as signed.
5. Add a **Transfer note** with the reason or a reference if needed, then choose
   **Transfer**.
6. The source MAH and selected agreements are marked **Transferred**. The portal
   opens the receiving MAH and records the source, date and note under **Transfers**.
7. To display a historical agreement on the receiving MAH, open **Contract → Manage
   agreements** and link it. Use **Actions → Archive MAH** on the source when ready;
   its transfer history remains available.

For example, select **Celgene GmbH** as the source and **Bristol-Myers Squibb SA**
as the recipient. Select the signed Celgene agreement if it is part of the transfer;
keep the receiving MAH's continuing agreements signed.

## Review MAH invoicing and contracts

**Eligible for invoice** is in the MAH's **Invoice information** card. It means
invoices are addressed directly to this MAH. Otherwise, record the parent company
that receives invoices on its behalf. This field is also available as a view
condition and list column.

The **Contract** card displays current statuses and signing dates from linked
agreements. Changes to an agreement are reflected on its linked MAHs. Use
**Manage agreements** to correct assignments or **New agreement →** to create one.

## Review historical self-declarations

Open **CRM → Self-declarations** to search by declaration or MAH. In **Configure
view → Conditions**, filter by declaration year, unassigned records or repeated
source labels. A MAH's **Related records → Self-declarations** link opens its history.

**Data year** is the year of the sales and pack counts. **Invoice year (derived)**
is the following year: the 2027 invoice uses 2026 data. A declaration shows reported
RX packs sold, sales and quantity groups, and imported billing amounts. Repeated
labels may refer to differing source rows; review the rows individually.

**Imported status** is the last retained Airtable stage. It does not confirm a new
send from Operations. Views for live outstanding responses will follow the
invitation/send/receipt workflow once that lifecycle is connected.

### Preview the annual fee

In a declaration, **Fee calculation preview** shows the base fee, quantity-related
amount, sales-related amount and total in CHF. It uses the imported base fee when
present and labels the CHF 1,500 default when blank. Historical billing preserves
the original Airtable amounts.

## Prepare self-declaration invitations

1. Open **Workflows** and choose the data year. The invoice year is the following year.
2. Use **Preview candidates** to review current MAHs with a signed agreement and
   **Eligible for invoice** enabled. Existing declarations and drafts appear as
   already present.
3. Choose **Create drafts**. Each new draft has a unique form link.
4. Under **Review drafts**, open each draft and verify all recipients, including
   any Airtable SPOC suggestion. Multiple recipients are supported: enter one
   address per line or separate addresses with commas. The draft contains its form link.
5. Choose **Approve for sending** once the details are ready. Reopen an approved
   draft if corrections are required. Approval records the review; delivery is a
   separate step.

The workflow dashboard compares the selected cycle with the preceding data year.
Open **Previous cycle comparison** for imported statuses and MAHs that entered or
left the eligible list. An Airtable status shows the last recorded declaration
stage; use delivery records to verify actual sends.


## Personal views in record and report tables

Use **View** to choose a saved personal view or **All records**. Direct search
stays above the table. **Configure view** opens the right-hand toolbox:

- **Conditions**: choose the report scope, add conditions and set the sorting.
- **Columns**: show/hide columns and change their order with the arrow buttons.
- **Save view**: give the configuration a name and optionally make it your default.

**Apply** previews changes; **Save view** keeps them for your account. Products,
Batches, Organisations, Locations and Exceptions apply conditions across all
matching records before pagination. Related batch/location tables work the same
way. Other report tables filter the retrieved report scope, as indicated by their
row counter; change the report period/scope to retrieve different data.

**Actions → Download CSV** downloads the table's current view: displayed data
columns in their current order, matching rows and the applied sorting. A saved
view is not required. Column changes take effect immediately; apply pending
filter/search changes first if you want them to change the displayed results.
Paginated views export all matching pages. Report exports retain their current
report period/scope and do not request additional external reports. Selection
checkboxes and action links are excluded. The file contains UTF-8 text with
quoted comma-separated fields; source identifiers retain their leading zeros
in the file. Spreadsheet applications may still apply their own import formats.

Choose **Actions → Download Excel** when opening a view in Excel. The `.xlsx`
file stores GTINs, GLNs, serial numbers, batch identifiers and other text fields
as literal text, preserving leading zeros and long identifiers. Reported numeric
columns such as Packs remain numeric where Excel can represent them faithfully.
Values beyond Excel's numeric precision remain text. The workbook retains the
same selected columns, row scope and order as the CSV, with a frozen header and
Excel filtering. Oversized cells are rejected rather than silently truncated.

CSV itself carries no column types. Quoted CSV values can still be converted by
Excel on opening. For external files, import through **Data → From Text/CSV** and
set identifier columns to **Text**, or disable the applicable automatic conversions
in supported Excel versions. Formatting an already rounded long number cannot
recover discarded digits; reimport the original source. See
[Microsoft: keeping leading zeros and large numbers](https://support.microsoft.com/en-us/excel/keeping-leading-zeros-and-large-numbers).

The download shows progress and **Cancel download**. An incomplete or failed
retrieval does not produce a partial CSV. If source/count changes are detected,
reload the view and retry. A generation receipt records staff identity, UTC time,
source table, selected columns, view hash, row count and file checksum; it does
not claim that your browser saved the file. Formula-like text receives a leading
apostrophe so spreadsheet applications treat it as text.

**Actions** also opens existing table actions, initially closed.
Select records in the table, then choose an existing action. Selection applies
to the displayed page. Existing confirmation and audit requirements still apply.
Close either toolbox with **Close**, Escape or the backdrop on smaller screens.

## Review End-user registrations

Open **Workflows → End-user registrations**. The dashboard separates:

- **Awaiting email confirmation**: the submitted mailbox has not been confirmed.
- **Needs review**: confirmation was received; your review is required.
- **Ready for NMVS**: you approved the review; create the organisation manually.
- **NMVS created**: the manual creation and organisation ID have been recorded.

Open a registration to review the organisation, address, software and contact.
The provisional CRM End User and contact already exist; follow their links to
correct details. Possible duplicate names/GLNs require explicit checking. An email
confirmation does not verify an organisation's licence or authorisation.

Open the **Actions** toolbox and choose **Approve review · ready for NMVS**. You
can then use **View temporary security data** to obtain the exact security question
and answer for manual NMVS entry. Access is logged. After completing the work in
the NMVS, enter its organisation ID and choose **Record manual NMVS creation**.
This does not make an API request to the NMVS. The temporary question/answer is
erased at that point, on rejection, or through expiry cleanup; do not copy it into
review notes. Link the CRM End User to its NMVS organisation once a Snapshot
contains that organisation.

**Reject registration** and **Reopen review** require a reason. Reopening never
undoes a real NMVS organisation or restores erased security data. CRM changes after
approval require another review. If a contact email was changed, the old mailbox
confirmation does not verify the new address.

For pending confirmations, **Resend confirmation email** replaces the old link.
With direct Connect delivery, the status is updated immediately and no manual
synchronisation is required. A link expires after 24 hours; temporary registration security
data is retained for at most seven days internally. If it has expired, request a
new registration/secure collection as appropriate. `Accepted by SendGrid` is not
proof of delivery. An uncertain mail outcome is not automatically retried.

SMVS Connect forwards registrations to a limited private API; storage and mail
delivery run inside Operations. Connect has no access to the CRM interface or
the Operations database.

Since 2026-11-10 new registrations use the signed Tally webhook to SMVS Connect.
The user disabled the former direct Tally-to-Airtable integration and Operations
now runs the automatic confirmation-mail worker. It normally checks the queue
every 30 seconds. The full real-form smoke test passed, including automatic email delivery,
explicit confirmation and the transition to Needs review.

One synthetic registration named **SMVS Connect Acceptance Test 2026-11-10** is
retained for cloud acceptance. Do not approve it as a real organisation or create
it in NMVS. Previously sent legacy links still depend on the old PHP confirmation
endpoint and Airtable token store, which must remain available until those links
have expired or been reconciled. Make involvement in the former mail flow was
not confirmed; Tally's direct Airtable integration was the disabled producer.

### Permanently delete registration test data (administrators)

Open **Workflows → End-user registrations**, select the test registration and open
**Actions → Permanently delete**. Select **Also delete the linked CRM End User and
contact** to remove the complete test registration. Tick the explicit confirmation
and choose **Permanently delete registration**. This cannot be undone.

Without the CRM option, only the registration workflow is erased; the CRM records
remain and their registration link is removed. In CRM, administrators can also use
**Actions → Permanently delete** on End Users, contacts and MAHs. Linked registrations and contracts still require explicit review. With migration
0043, deleting a contact removes its contact assignments while retaining MAHs
and End Users; a source fingerprint prevents recreation by a repeated import.
This contact correction is local-only at the 2026-11-10 checkpoint.
Archive remains the reversible alternative.

Erasure removes form data, temporary security answers, confirmation tokens and
workflow notes. Old confirmation links stop working. Operations retains a minimal
deletion audit (operator ID, time, record type/ID) and a technical receipt marker
so Tally retries cannot recreate the erased registration or send another email.
An email already being sent must finish before deletion. NMVS organisations are
not deleted. Existing source imports and backups follow their own retention policy;
this action does not remove external Tally submissions or previously sent email.

To start directly from a CRM End User or contact, choose **Actions → Review
permanent deletion**. If a registration is linked, the review lists its End User
and contact and offers **Delete registration and linked CRM data**. Confirm the
complete scope explicitly. No separate removal of the relationship is necessary.
Use **Review registration or delete the workflow only →** if you want to keep the
CRM records. If deletion is blocked, the portal shows a readable explanation and
keeps all records intact.

### Imported MAH contact assignments

MAH **Contacts** uses persisted CRM contact IDs for SPOCs and Alert contacts.
When MAHs or Contacts are imported, missing role assignments are populated from
unique Airtable record-ID or exact imported-label matches. Several contacts may
share a mailbox and remain separate contacts. Existing manual choices, including
an explicitly empty selection, are retained. Archived MAHs/contacts and unreviewed
registration contacts are not automatically assigned. Ambiguous or missing
references are shown in the Contacts card for manual review; no partial list is
silently accepted for an unresolved role. **Imported contact references** retains
the original source wording for comparison.

### Review the proposed End-user investigation

In **Exceptions → Root cause analysis**, open **Shared investigation → Preview
End-user investigation**. This NMVO/Administrator-only page previews a limited
participant projection and versioned EMVO-guided checks. Choose **Pharmacy** or
**Wholesaler** and select **Update preview** to review the relevant workflow.

The view includes SAI product context, provided/stored batch, the full transmitted serial
number, its character count and the source observation. Where a retained exact same-location A7
Export/Destroy sequence is established by the existing evaluator, it can show the
successful operation and rejected repeat without exposing raw report rows or
other locations. Questions reference the supplied EMVO steps. Internal RCA notes
and raw error messages are excluded from the participant content. Matching Snapshot
batch constraints are shown separately for the provided and stored batch, with raw
format codes. They are reference observations, not proof of authenticity. A7 also
previews participant assessment choices and a separate known-issue flag; response
entry is not yet implemented.

This is a local, read-only design increment: organisation/location/recipient scope
still needs staff review. Intermarket responsibility and changed local assessment
basis are flagged internally. The workflow selector is a guidance choice, not an
identity or permission assignment. No invitation, case publication, contribution,
closure or deadline calculation is performed by this page. Opening the preview
does not retrieve reports; the explicit evidence-preparation action is described below.
Case persistence, the working-day calendar and scoped external access follow after
review of this projection.

### Automatic investigation pre-checks

Open **Exceptions → Root cause analysis**. **Intelligence · Automatic pre-checks**
shows the next evidence step, with expandable results for batch comparison,
Snapshot availability and serial length. A discrepancy is a lead to investigate;
a matching value does not establish authenticity. The reference Snapshot date may
differ from alert time. No value is repaired or confirmed automatically.

Where useful, **Prepare pack evidence** queues one exact-pack report in the
background. Existing reports or pending requests are reused across related
exceptions. Follow **View report processing →** to inspect progress; the report
worker must be running. A2 instead links to **Review upload history →**; a serial
length discrepancy calls for comparison with the pack first. IMT cases are not
automatically fetched by this action. An explicit refresh remains available in
**Pack audit trail** after reviewing an existing report's coverage.

Opening RCA or the staff-only participant preview does not request a report,
save a review or change work status. The participant preview is still not a public
case or an editable participant response form.

### Running imports in the local test system

**Run now** creates a durable import request. It does not start a scheduler
process. An active import worker must take the request; the Imports page shows
whether it is connected. **Manual import worker connected** means manual requests
can run but automatic imports are not being started. Without a worker, the queued
request remains visible and can be cancelled.

A normal **Daily Snapshot → Run now** now includes publication of Products,
Batches, Organisations and Locations using the already selected SAI reference.
It does not silently select a different SAI import. Older inputs and implicit
same-day corrections remain blocked. A historical Snapshot backfill only retrieves
and stages its selected date; it does not roll the current catalogue backwards.
Acquisition success and publication success are distinct: a publication failure
is recorded against the import execution with its acquired source job retained.

In **Imports → Run history**, expand **Failure details** on a failed or interrupted
execution. It shows the execution ID, recorded error code, elapsed time (or time
until an interruption was detected), an explanation and suggested checks. Where
available, acquisition/processing records show the last recorded source status
and failure stage. An explicitly linked source job is distinguished from activity
found only in the same time window; ambiguous activity is not assigned. A hard
worker termination may leave no exact cause recorded. Source processing success
alone does not establish that publication completed. Expanding details is read-only.

For local review, start the portal and `.venv/bin/python -m app.integration.scheduler --serve-manual` as separate processes. This worker
processes explicit manual import and evidence requests without triggering overdue
automatic imports. Normal scheduled operation still uses `--serve`.

### Search when linking an End User to an NMVS organisation

In **CRM → End Users → NMVS organisation → Link organisation / Edit link**, use
**Choose organisation** to open a searchable selection dialog. Search by name or
NMVS organisation ID; letter case and accents do not prevent a match. **Use
selection** updates the draft choice; **Save link** persists it. **Cancel** or
Escape closes the dialog without applying the draft. With JavaScript disabled,
the standard selection list remains available.

The displayed Snapshot date is the published participant reference. The Daily
Snapshot is generated once daily: retrieving it again does not include an
organisation created after that report was generated. A newer acquired/staged
report is also not the same as a newer published participant reference. Existing
one-to-one CRM links remain protected; an organisation assigned to another CRM
End User is unavailable for a second assignment.


### Local trial: MAH declaration lookups and Data integrity

In MAHs, open **Configure view → Lookups → Self-declarations**. Add up to eight
field/operator/value conditions and select **All conditions (AND)** or **Any condition
(OR)**. These conditions choose declarations within each MAH; the Conditions tab
filters MAH rows. Empty conditions include all related declarations.
Choose **Unique match** (exactly one candidate), **Minimum (Min)** or **Maximum (Max)**
on SD year or RX packs sold. For the latest declaration use **Maximum → SD year**;
for a fixed year add **SD year is 2025** and use **Unique match**. Numeric empty values
are excluded from Min/Max; reported zero remains zero. Ties and duplicate MAH/year
records never supply arbitrary values. A filter cannot hide the duplicate source
of a selected year. The separate Data integrity check still reports all duplicates.
Select **Columns to display** directly under **Lookups**. Each checked field
appears immediately as a lookup column; there is no second visibility choice.
**Columns** contains only fixed MAH fields and controls their visibility/order.
Lookup columns follow the fixed fields. Resetting fixed columns does not change
lookup choices. **SD year** and **Selection result** are optional and can be
unchecked. For example, choosing only RX packs sold adds only that lookup column.
Ambiguous selection and duplicate source errors are shown directly in affected
lookup cells, even when Selection result is hidden. Apply or save the view to
retain the complete selection for reload and exports.
If an output is used by MAH conditions or sorting, remove that dependency before
removing the output. All outputs refer to one declaration; Min/Max do not aggregate
individual columns. The highest year is not a receipt/approval status. Conditions,
sorting and CSV/Excel exports use the applied selection across all export pages.
Existing highest/fixed-year personal views remain readable and are converted when
saved through the new editor. This first implementation has one Self-declarations
lookup per MAH view; independent named lookups and contract lookups are future work.

Opening a SPOC or Alert contact from a MAH or End User adds **← MAH: Name** or
**← End User: Name** beside **← Contacts**. The new link returns to that exact
parent's Contacts section and retains its original view context. It survives edit,
save and cancel, and opening the link in a separate tab. Previous/Next steps through
that parent's contacts. Direct entry from Contacts has no fabricated source link.
MAH links to individual agreements and selected self-declarations also carry a
source-record return link. Missing source records omit the contextual link.

Save this experiment as a separate personal view, for example **Lookup trial**,
so an existing working view need not change. The MAH detail shows the same lookup
scope with a source-record link where unique.

**CRM → Data integrity** reruns read-only checks. Choose the data year, check,
assessment or record type and use **Run checks**. Duplicate SDs are checked across
all years; missing SDs are review items in the current signed-agreement/invoice-
eligible population. No deadline or historical obligation is inferred. Contact
links retained only in the import need review; they are not silently treated as
confirmed assignments or automatically deleted. Open the linked records to review
findings. Rerun checks after an explicit correction.

The experiment applies no schema migration. Before reverting its Git branch,
remove separately saved trial views/defaults (or restore their private pre-trial
backup). A Git checkout does not restore database view configurations. New
assigned duplicate declarations are rejected by the import service; do not use
this trial to silently merge the existing conflicting historical records.

# SMVS Operations User Guide

Open this guide using **?** in the portal header. This guide describes the current
CRM review tools and self-declaration preparation workflow. Application controls
are in English; imported names, messages and evidence retain their source language.

## Portal layout and text size

Module tabs appear above the page title. Catalogue tabs switch between **Products**
and **Batches**; participant tabs switch between **Organisations**, **Locations**
and **Activity**. Detail-view tabs, such as **Root cause analysis** or **Original
data & evidence**, also appear above the title. Filters and data remain below it.

Lists and detail cards use the same text hierarchy across the portal: data values
are more prominent than button labels, while section headings stay compact.
Dashboard figures retain their larger size. Use **A−** and **A+** in the header
to scale the interface, including data and controls, together.

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

Where available, **Actions** opens the corresponding toolbox, initially closed.
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

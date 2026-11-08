# SMVS Operations User Guide

Open this guide using **?** in the portal header. This guide describes the current
CRM review tools and self-declaration preparation workflow. Application controls
are in English; imported names, messages and evidence retain their source language.

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

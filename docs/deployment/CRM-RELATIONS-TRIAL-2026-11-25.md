# Local CRM relation and integrity trial — 2026-11-25

## Boundary

Branch: `experiment/crm-lookups-integrity`, base `4f93b93` /
`pilot-2026-11-25-dev`. This is a local pilot experiment (CHG-011), not a server
release or approved QMS baseline. No production files, schema or data are changed.
No notifications, participant workflows or automatic repair are introduced.

URS-001 draft v0.11 records URS-111–113. FRS, RA and RTM reconciliation is deferred
until trial feedback, with explicit tasks in the implementation list. Existing
Word requirements drafts are not silently revised or approved by this change.

## Review the trial

- In MAHs, open **Configure view → Columns**. The **Relation lookup ·
  Self-declarations** group chooses highest data year or a fixed data year.
- Show the desired **Self-declaration · …** columns. Data year and Selection
  result remain visible when lookup data columns are shown. All values come from
  one selected source; no column silently falls back to another year.
- Apply, filter, sort and save as a separate **Lookup trial** view. Open a MAH or
  the linked declaration to inspect the source. Try a missing year and a known
  duplicate: source values remain empty, with an explicit selection result.
- CSV/Excel exports collect the applied relation selection across matching pages.
  Pack counts remain numeric where faithful; a reported zero remains zero.
- Open **CRM → Data integrity**. Source filters are under **Configure view →
  Conditions** when the shared table controls are active. **Run checks** reloads
  the selected source scope; findings themselves are never persisted as repairs.

Duplicate SD checks include all linked MAH/year pairs, including historical
records. Missing SD review uses a specified year and current, non-archived MAHs
with a signed agreement and invoice eligibility. This reuses current invitation
eligibility, not historical legal/contractual applicability or an overdue policy.
Role requirements use current MAHs and available, non-provisional contacts.
Imported-only links and orphan contacts are review items. A contact can fulfil
both required roles. Duplicate GLN/UID findings require review rather than an
assumption that two business entities must be merged.

## Data integrity and remaining enforcement work

The import service locks MAHs before reading assigned MAH/year business keys and
validates the complete plan before adding declarations. A conflicting assigned
pair aborts that business import; retained staging rows remain available for
review. Exact repeat imports remain idempotent. Repeated display labels across
different years remain permitted; display labels are not identity keys.

Existing historical duplicates remain unchanged. Add a database-level unique
constraint only after explicit cleanup and verification of future creation and
assignment paths. The trial adds no migration and does not claim that arbitrary
external SQL writers are constrained by its import-service guard.

## Revert safely

A private local backup of the two existing MAH views/preferences was captured at
`tmp/crm-relations-review/pre-trial-mah-views.json` before this trial. It is ignored
by Git and is not a controlled QMS backup. No source records were corrected.

1. Save trial settings as separate named views; avoid replacing established views.
2. Before reverting code, remove only trial views through **Save view → Delete
   view** and undo any trial default. If an established view was edited, restore
   its previous configuration from the private backup after reviewing intervening
   changes; do not overwrite unrelated/new work.
3. Stop the local development portal and switch back to the base branch/checkpoint.
   Restart the portal. No schema downgrade is needed (both use local schema 0053).
4. Verify sign-in, existing views and record counts. A Git switch alone does not
   revert saved database configurations. Production is outside this procedure.

## Verification

CHG-011 records 521 passing Python tests and three passing Node tests from a
clean indexed export, successful application import, changed-file lint/syntax
and whitespace checks. Browser review verified a saved 2024 lookup view and an
exact 48-MAH CSV across two pages, plus the integrity page at 1500/650 pixels.
Data year/selection-result requirements are also enforced for visible lookup
columns. The browser
review uses an isolated SQLite fixture with synthetic MAHs/declarations and no
scheduler or external delivery. The existing local operational database is used
only for read-only checks and the pre-trial view backup during this work.

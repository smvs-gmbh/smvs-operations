# CRM retention and erasure

## Current portal actions

- **MAHs**, **Contacts** and **End Users** support reversible archiving. A contact's existing assignments remain visible. An archived contact cannot receive a new assignment or be suggested for a new declaration invitation.
- **Agreements** retain their contractual lifecycle status and document history. Excluding an attachment is reversible.
- **Self-declarations** retain historical declarations and imported billing evidence.
- **IT Suppliers** are currently sourced from the staged Airtable export. **Import review** shows staged evidence and matching results.

## Proposed retention and erasure process

Article 6 paragraph 4 of the Swiss Federal Act on Data Protection requires destruction or anonymisation once personal data is no longer needed for its processing purpose. Set retention periods by purpose and record category. An archive date helps schedule a review and does not determine lawful retention by itself.

1. **Review archived contacts.** Use loss of purpose, such as a person leaving the contact role, as the review trigger. Check whether an operational need, an applicable retention obligation or a documented legal hold still applies. Record the reason, owner and review or expiry date. Review archived contacts regularly and handle individual erasure requests when received.
2. **Separate CRM data from required evidence.** Check accounting records under Article 958f of the Swiss Code of Obligations. The listed accounting records are retained for ten years from the end of the financial year. Check whether each declaration or attachment forms part of that evidence. Keep any necessary evidence under restricted access.
3. **Trace copies and references before execution.** Review MAH and End User assignments, imported Airtable rows and original CSV artifacts, IT Supplier references, declaration recipients, retained documents and any external system holding copies. Removing a CRM row alone leaves data in these sources. Review pending invitation recipients if a SPOC leaves.
4. **Erase or anonymise on approval.** Design an administrator-only action with a preview of the affected records. Remove operational references, erase or irreversibly anonymise data without a continuing purpose, and record a minimal decision trail. Track backup expiry and reapply erasures if a backup is restored. Prevent later imports from recreating erased personal data.
5. **Set and review category rules.** Agree the trigger, review cadence, exceptions and the treatment of copies for each category before automating erasure.

The current portal implements reversible archiving. The erasure action and automated retention rules are pending.

- [Swiss Federal Act on Data Protection, Article 6](https://www.fedlex.admin.ch/eli/cc/2022/491/de#art_6)
- [Swiss Code of Obligations, Article 958f](https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de#art_958_f)


## New registrations

The registration workflow keeps security questions/answers outside normal CRM
profiles and raw import artifacts, as temporary encrypted values. They are erased
after manual NMVS creation, rejection or expiry cleanup. The isolated public intake
also clears confirmed payloads after durable core acknowledgement. See
[end-user registration](end-user-registration.md) for worker cleanup, Tally copies
and backup-retention limitations. Core CRM identity data and the minimal workflow
audit still require their own purpose-based retention/erasure decisions.

## Administrator erasure of registration test data

Administrators may permanently erase a direct-mode registration and, optionally,
its unshared CRM End User/contact from the Actions toolbox. Ordinary NMVO users
retain archive/review capabilities but cannot erase. Minimal technical duplicate
markers and deletion audit IDs remain; form contents/security data do not. The CRM
also offers guarded deletion for End Users, contacts and MAHs, blocking linked
registration records. From migration 0043, standalone contact erasure detaches
its live contact assignments and suppresses recreation by source fingerprint;
MAHs and End Users remain. This correction is local-only at the 2026-11-10 checkpoint. This feature is
not a complete data-subject erasure across retained source exports, Tally, email
and backups; those remain subject to the wider retention procedure.

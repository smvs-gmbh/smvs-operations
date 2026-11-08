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

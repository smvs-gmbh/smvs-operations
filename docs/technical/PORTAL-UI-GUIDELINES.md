# Portal UI conventions

Use the shared portal layout and styles for new pages. Follow the [UI language rules](../../AGENTS.md) for British English, ISO dates, UTC timestamps and original source values.

## Links, buttons and navigation

| Purpose | Convention | Example |
| --- | --- | --- |
| Open a related record, evidence view or workflow from a detail page | Use a descriptive link with a trailing `→`. | `Inspect pack audit trail →`, `View local audit trail →` |
| Return to a parent view | Use a leading `←` and name the destination. | `← MAHs` |
| Open a record from a results table | Link the record name or ID directly. | MAH name, Alert ID |
| Switch between module views | Use named tabs or subnavigation with the current destination indicated. | **MAHs**, **Contacts**, **Import review** |
| Open section editing or leave it | Use the short links **Edit** and **Cancel**. Give repeated **Edit** links an accessible name that identifies the section. | `Edit address` |
| Submit a form or change state | Use a button with a verb that describes the action. | **Save changes**, **Reopen selected exceptions** |

Keep the destination or action clear from the text. Put the arrow after the text inside the same link. Use an anchor for navigation, including links to a review page before a state change. Submit the state change with a form button.

## Page layout

- Use the shared sidebar and page shell. Place the shared record navigation bar above the title on detail pages opened from a list. Align the back link on the left and **← Previous** and **Next →** together on the right. Use the same link typography throughout. Keep unavailable directions visible without a link.
- Step through the originating list in its current order and across page boundaries. Preserve its search and filters, including linked or archived scopes. Within a related-record list, keep navigation scoped to that parent. Keep the record navigation distinct from module navigation and record tabs. Use a back link alone for standalone forms and disable record switching while editing.
- Put the module label and record name or identifier immediately below the record navigation.
- Keep module navigation in a consistent position. Use local tabs when one record has several distinct views, as in Exceptions. Use module subnavigation for related directories, as in CRM.
- Use tables for lists of records and reuse the shared pagination. Place bulk actions above the results and indicate the scope of selection.
- Use named panels for groups of fields on detail pages. Put the smaller, muted label above the larger, darker value. Use up to three columns for short values and stack the fields on narrow screens. Give summaries, addresses and long values room to wrap naturally. Keep identifiers such as GLN and UID together.
- Preserve field groups in edit mode. Open editing explicitly per section, save that section only and offer **Cancel** back to the read view. In a selection dialog, separate confirming the selection from saving the record.
- Keep source values and evidence identifiable. Use the relevant source label, timestamps and links to the original evidence. Keep local assessment and work status distinct from source status.

## List pages

Use [Products](../../app/portal/templates/products.html) as the reference layout. Put these elements in order:

1. A short category keyword, such as **Catalogue & references**, above the page title and a one-sentence description. Use the shared `list_heading` macro.
2. A compact source-status strip where relevant. Label snapshot dates, import timestamps and coverage accurately. Use UTC for timestamps. Module or view tabs may sit between the heading and list content.
3. A small dashboard with two to four relevant metrics. Use the existing metric card styles or the shared `list_metrics` macro. Label the scope of each count, such as the published snapshot, the current directory or the filtered results.
4. The results panel. Place its title and result count above the search and filter row, with the table directly below. Keep list filters inside the results panel. Use the available filter dimensions for report and history tables. Short fixed reference tables can omit search.
5. Pagination below the table where needed. Charts and additional evidence tables can follow the primary results.

## Reference pages and shared assets

- [Exception detail](../../app/portal/templates/exception_detail.html) and [root cause analysis](../../app/portal/templates/exception_analysis.html) show contextual links to related records and evidence.
- [MAH detail](../../app/portal/templates/crm_mah_detail.html) and [contact detail](../../app/portal/templates/crm_contact_detail.html) show read views and section editing.
- [Shared navigation macro](../../app/portal/templates/macros.html) and [navigation helper](../../app/portal/record_navigation.py) provide the common record bar and neighbouring records.
- [Base template](../../app/portal/templates/base.html), [shared template macros](../../app/portal/templates/macros.html) and [portal stylesheet](../../app/portal/static/portal.css) provide the shared shell and components.

Check new pages at narrow and wide widths and with the portal’s text-size control. Verify that keyboard users can reach links, buttons and dialog controls, that the active view is identifiable and that longer values stay readable.

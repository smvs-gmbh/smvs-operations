# EMVO best practice and SMVS investigation and closure policy

Date: 2026-11-10. The product owner identifies the supplied **EMVO-00306 Best
Practice on Alert Handling** copy as the gold standard for Shared Alerts Management.
It governs the investigation content; NMVS Alerts product manuals are secondary
UI/workflow references. This is a software/product mapping of the supplied document,
not a claim that every EU obligation automatically applies as Swiss law.

## Source identity and precedence

- Supplied file: `EMVO-00306_Best Practice on Alert Handling v2.2 (clean).docx`.
- SHA-256: `696c295b4f41def944935cceeb3cfb5feb776f6bf0c703ef18963d3aea5b9bee`.
- Owner confirmation: this is the authoritative content for the project, reiterated
  2026-11-10. The filename identifies v2.2; the internal revision table includes an
  uncompleted 3.0 entry with a placeholder date. Do not invent an effective date
  or substitute another edition based on that metadata.
- Section/step identifiers below refer to this exact supplied content. Its references
  identify 3.7 for IMT, 3.8 for NMVO, 3.9 for EMVO, 3.10 for status and 3.11 for closure.

Use the following order when building the product: applicable approved Swiss
procedures and responsibilities; this owner-designated EMVO content as the technical
baseline; the explicit SMVS closure-authority choice below; NMVS Alerts manuals as
examples. Any further national deviation requires a recorded decision rather than
being introduced implicitly as UI simplification.

## The explicit SMVS choice: central NMVO control and closure

Section 3.11 already gives closure by the relevant NMVO as the general rule. It
also permits MAH closure under stated conditions and allows End-users to be
specifically authorised to close certain alerts. **SMVS will not delegate these
closure rights to End-users or MAHs in this platform.** This narrows the optional
closure paths; it does not remove their investigation and feedback responsibilities.

- The responsible NMVO controls the case, monitors outstanding checks, assesses
  findings and makes the final closure or escalation decision.
- End-users/MAHs can identify a cause, rule out a cause on their side, provide
  evidence, take corrective action and respond to a resolution proposal.
- A participant's completed task or readiness response cannot close an alert.
- A “no root cause on my side” response records an investigation result for that
  participant; it does not establish that the overall cause is known or that the
  pack is authentic.
- Capture actor, authority, reason, completed/relevant checks, findings, evidence
  versions, remaining concerns and the exact Alert IDs in the NMVO decision.
- At pilot launch, closure is an authenticated NMVO action. Any later automatic
  closure requires an explicitly NMVO-approved, versioned policy, validated scope
  and audit; it is not delegated participant authority.

For IMT, **responsible** means the initiating NMVO under section 3.7. SMVS must not
claim formal closure authority for foreign-initiated alerts merely because Swiss
pack data fulfilled the query. It can complete its own support/local work and
record that disposition separately.

## Traceability to product behaviour

| Source | Meaning for Operations / Connect |
|---|---|
| Section 2, scope | This procedure addresses NMVS Level 5 alerts with Alert IDs. Keep L3/L4 exceptions separate; importing them must not automatically label them potential falsification cases or create the same closure workflow. |
| 3.1, investigation principle | Investigate data, technical and procedural explanations systematically. Intelligence proposes and links evidence; a matching pattern is not itself a confirmed root cause. |
| 3.2, communication | Capture case findings or a progress report promptly and within two working days of the alert. Keep open questions and updates; the deadline is not automatic closure. |
| 3.3, End-User-01a | Present the approved pack-handling guidance and record the pack's availability/handling separately. Avoid repeated scanning without a justified check/correction. Alert closure and return to saleable stock are distinct decisions. |
| 3.3, End-User-01c/01d | Route A2/A3/A52/A68 to comparison/manual-verification guidance where appropriate. Do not recommend manual entry for pack-state alerts or when displayed scanned data already matches printed data and it adds no information. |
| 3.3, End-User-02a | Investigate a procedural cause, including repeated decommissioning and adjacent-barcode reads; same-location repetition must be established, not assumed. Different-location evidence requires NMVO involvement. |
| 3.3, End-User-02b/02c | Investigate scanner and software/IT causes as applicable; use known CRM software/context to avoid redundant questions. Retain the corrective action and evidence that it worked. |
| 3.4, wholesalers | Apply End-user steps with wholesaler-specific additions. Wholesaler A7/A24 pack-state cases go to the NMVO; suspected upload problems involve MAH and NMVO. A MAH acting via a wholesaler connection follows the End-user/wholesaler process. |
| 3.5, MAHs | A2/A3 generally require MAH investigation unless known to be End-user error. A7/A24/A52/A68 do not automatically require MAH investigation: apply the stated originating-transaction/request exceptions. Prepare this routing now, even before Hub integration. |
| 3.7, IMT | Initiating NMVO ensures investigation. Fulfilling NMVO supports on request and does not change the formal alert status. Preserve market roles and restrictions on identifying End-users. |
| 3.8, NMVO role | Monitor results, intervene when needed, document the conclusion and notify the appropriate parties. Early intervention is possible for unusual/urgent cases; it is not a forced two-day wait in a suspicious case. |
| NMVO-06 | Review product/batch and location/software patterns. Request confirmation/corrective action, rather than treating correlation as proof. Monthly prevention reports complement this case monitoring. |
| 3.10 | Completed investigation plus an established data/technical/procedural explanation and no indication of falsification supports Closed (falsification ruled out). Missing essential information keeps the investigation open. |
| 3.10/3.8, suspected falsification and escalation | No established explanation after the relevant investigation is not a benign “unknown” closure. Distinguish suspected falsification from escalation to obtain missing cooperation. Keep the latter under investigation. |
| 3.11 | Use the NMVO closure route and omit optional participant closure rights under the explicit SMVS choice. |

Preserve any applicable national qualification to pack handling, exemptions and
notification in the approved Swiss guidance. Do not translate the above mapping
into unconditional medication-supply advice or invent a universal quarantine period.

## Timing and monitoring

Make time targets visible in Operations and Connect: alert occurrence time,
received time, expected feedback date, last substantive update, next action, owner
and overdue status. Define working days through an approved Swiss business calendar
and time zone; do not silently implement two working days as 48 hours. An invitation
created late does not reset the original alert-based target. A progress update can
meet the feedback requirement while the investigation remains open.

Section 3.8 describes allowing End-users/MAHs to perform their initial investigations
before ordinary NMVO intervention in the first two working days, with earlier
intervention for unusual cases. SMVS can monitor, assemble evidence and control the
workflow immediately. Ordinary follow-up requests/reminders should reflect this
sequence; early targeted intervention records the reason. Existing phone/email
feedback is attributed and captured rather than requiring duplication in Connect.

Historical backfills expose original occurrence and arrival times and enter an
NMVO review queue. They must not trigger an uncontrolled retrospective mail or
escalation flood. Agree reminder/escalation rules before activating them.

**A monthly MAH/End-user report is supplementary.** It can group known recurring
causes and prevention actions, but cannot silently replace timely investigation,
a case progress report, a missing-data request or urgent escalation. If the Swiss
voluntary-serialisation context requires a different A2 handling policy, record it
as a further explicit Swiss policy decision; do not imply that monthly-only handling
is identical to this baseline or automatically close A2/A3 cases as harmless.

## Three independent states

| State | Meaning and authority |
|---|---|
| Local Exception work | Open / To do / Resolved locally. Manages the SMVS work list, including no further local action where justified. This can be complete without asserting a completed formal alert investigation. |
| Alert investigation outcome | Under investigation / Closed - falsification ruled out / Suspected falsification. Includes reasoned NMVO decisions; escalation for missing cooperation leaves the investigation open. |
| External-system acknowledgement | Not connected / Pending / Sent / Confirmed / Failed. Only a confirmed adapter result establishes an external update; it is not inferred from a local button or participant response. |

The product objective includes **actual NMVO-controlled alert closure**, not just
hiding rows. Phase 1 should therefore persist the NMVO's investigation outcome and
closure decision explicitly. Until the appropriate external integration is live,
label that decision's external state as Not connected; do not claim the NMVS or
AMS Hub has already changed. Add the external command and acknowledgement later
without changing who has closure authority.

A formal closure action requires a valid documented basis and no unresolved
falsification concern. “No response”, “same batch”, “not on my side”, a missing
upload search result, or a locally hidden row alone are not closure criteria.
Readiness responses are revision-specific and do not replace the NMVO assessment.

## Consequences for the pilot and MAH phase

1. Derive a versioned guidance catalogue from the actual End-User-01/02/03 and
   wholesaler paths. Each question/check points to its source step, applicability,
   existing evidence, possible answers and next action. Completed evidence can be
   referenced instead of being typed again; unresolved checks are not pre-confirmed.
2. Add the two-working-day feedback target, progress reporting and NMVO follow-up
   monitoring to the model before live participation. Set reminders under an
   approved policy rather than sending one notification for every alert.
3. Model distinct investigation outcomes and closure authority independently of
   existing local Resolved status. Test participant closure attempts are denied.
4. Show investigation steps and outstanding work to End-users using the permitted
   case view. A simplified interface must not omit relevant investigation branches.
5. Phase 1 can use existing reviewed channels for necessary MAH/NCA communication;
   deferring their portal/Hub integration does not defer their substantive role or
   case-specific escalation. Record outbound/inbound information and its provenance.
6. Add MAHs through the reviewed Hub protocol in phase 2, preserving End-user
   anonymity, recipient-specific evidence and the same NMVO closure gate.

## Review checks

Check that an End-user/MAH cannot close a case, overdue silence cannot close it,
and an unresolved concern cannot be hidden by a benign closure code. Verify that
local no-further-action on foreign IMT does not change initiating-market status.
Exercise scanner/procedural/IT paths, wholesaler A7/A24 routing, A2/A3 MAH exceptions,
a progress report without final findings, business-day calculation and the
separation between closure, pack handling and later Hub acknowledgement.

Related: [End-user pilot concept](Shared-Alerts-Management-End-User-Pilot.md),
[evidence-guided investigation](Evidence-Guided-Alert-Investigation.md) and
[Shared Investigation principle](Shared-Investigation-and-CRM-Proposal.md).

## National guidance comparison

The [NMVO guidance comparison](NMVO-Guidance-Comparison.md) records Austrian
AMVO-005-2.0 (including glossary) and selected Irish/German references. These
inform Swiss design; they do not override this EMVO baseline or SMVS closure
ownership. National deadline, escalation and dispensing rules require explicit
Swiss approval before implementation.

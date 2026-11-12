# A2 and A3 verification and intermarket analysis

Reviewed 2026-11-10 against the three historical specifications supplied by the
owner. This is a focused analysis of missing identifiers, intermarket routing,
upload completeness and their consequences for Shared Investigation. It is not
confirmation of the currently deployed NMVS release or a production rule change.

## Findings

A2 and A3 are related outcomes in a validation/routing process, not reliable root-
cause labels. A3 does not imply an exhaustive search across national repositories,
nor universally prove a known batch. A2 does not prove that a batch was never
uploaded. Separate the submitted identifiers, local validation, Hub routing,
fulfilling-market result, source audit and final API/alert representation.

The current Connect prototype must not claim that an IMT was performed solely
because the case is A3, or describe every A2 as an unknown batch in the Hub. Its
current A3/IMT and A2/no-batch examples are fictional selected branches, not generic
interpretations of their codes. Operation-code explanations need reviewed context.

## Source register and locator conventions

| Reference | Supplied file | Content/version observed | Relevant locations |
| --- | --- | --- | --- |
| H | `EMVO-00582 - EMVS European Hub Functional Specification.pdf` | Actual header: EMVS0647, version 18.0, Service Release 1.16, Approved; revision approval 2024-09-18 | 7.15.1, printed/PDF pages 212–215 |
| U | `EMVO-01509 - EMVS User Requirements Specifications (URS).pdf` | Wrapper/header: EMVO-01509 version 1.1 Draft; body header retains version 1.0 / 2022-04-21; retrieved 2024-08-07 | 8.1.10 / 5999, pages 112–113; 9.1.13 / 11053, pages 138–139; 10.4.1–2, page 192; 10.4.5 / 10148, pages 193–194; 10.4.7 / 18999, pages 195–196; 10.4.10 / 10905, pages 199–200 |
| N | `EMVS0033 - EMVS NBS Functional Specification V16.2.docx` | EMVS0033 version 16.2, Draft in rendered header; revision history 2024-06-24 | 3.1.2 Product Pack Data; 3.1.5.2 Verify Single Pack; 3.1.5.4 Request Intermarket Pack Verification; 3.1.5.5 Process Intermarket Pack Verification; 3.1.5.7 Validate Pack, Figure 36 |

All originals remain at the owner's supplied OneDrive specification paths; do not
copy the originals into the repository or publish them through Connect. SHA-256:

- H: `ca00300fb6c612597284a3faa1c8bb175dd1f528f57c8a2a190648ee9737ce60`
- U: `76f866ac69dfcac46e492998420495f3831a94747b4f760edd924697470a3ecf`
- N: `46e96cc15b15b069ae41af83aefc10d0b847817abf1a00cd3590bfaeee3d305f`

PDF page numbers match the printed main-body pages in H/U; H has 258 PDF pages
including signing history after its 256-page body. N was rendered read-only using
bundled LibreOffice for table/diagram inspection: 474 rendered pages. N page
locators below refer to that review rendering, not guaranteed Word pagination on
another machine. Section identifiers/headings and step conditions are primary.

## 1. Local serial lookup does not always trigger IMT

N 3.1.5.7 first validates the product, then the pack. For a missing pack, its step
4a returns A3 when **any** of the following applies:

- No batch number was supplied.
- The batch was found.
- The pack is not a candidate for an intermarket call.

Step 4b returns an intermediate A2 when the pack is missing, a batch number was
supplied, that batch is missing, and the transaction is an IMT candidate.
The shared validation introduction explicitly excludes bulk validation from IMT
candidacy. See Figure 36 and exception paths 4a/4b, review pages 186–191.

U 8.1.10 (5999) confirms the normal national verification case: product and batch
exist locally, serial does not; a serial-unknown alert is returned. U 9.1.13 (11053)
describes the corresponding supply/decommission case. U 10.4.5 (10148) and N
3.1.5.4 describe IMT initiation for an unknown product, or a known product with
both pack and supplied batch absent locally.

Consequences:

- A local A3 with a known batch is not evidence of an IMT lookup.
- An A3 may arise with an absent batch in a non-IMT-eligible transaction, including
  bulk validation. It is not universally equivalent to "batch exists, serial does not".
- A2 in local validation can be a routing result before the final reply, not the
  same event as the final L5 alert shown in the Exceptions API.
- API optional fields and manual-entry behaviour require their own context; do
  not collapse all transactions into the single-pack scanned-data branch.

## 2. What IMT actually does

H 7.15.1 steps 2–10 validates product and batch at the Hub, derives applicable
markets, excludes non-distribution/failed-distribution markets, and deterministically
selects a fulfilling market. It sends the request there and returns the result.
Footnote 15 explains that deterministic routing keeps transactions for a given
pack aligned with the market holding its most current state.

Retry branches select another applicable market for connection, authentication
or timeout problems. A normal pack-not-found result is its own terminal path
10d, returning A3 and the unique pack return code. It is not a documented serial
search in every national repository. U 10.4.2 similarly describes verifying in one
market where the pack was distributed, with fallback on connectivity/authentication
failure; U 10.4.10 describes serial-unknown in the fulfilling system.

Use **"not found in the fulfilling market for this request"** when that route is
established. Do not write **"not present in any NMVS"**. A boolean IMT flag alone
also does not reveal all visited systems or whether the local record represents
initiation versus fulfilment; combine business-process/market evidence and audit
where available.

## 3. A2 is broader than a batch never uploaded

H 7.15.1 explicitly returns A2 for at least these distinct conditions:

| Hub branch | What the specification says | Consequence for investigation |
| --- | --- | --- |
| 3a Invalid Batch | Batch validation fails; A2 returned | Check submitted batch and Hub evidence; do not infer who caused the failure |
| 4a Initiating market is the only market listed | A71 batch distribution fault audited; A2 returned | Batch/routing information exists; investigate distribution rather than simply assuming no upload |
| 6a All markets failed distribution | A2 audited and returned | Investigate failed propagation/distribution; an upload can exist |

Branch 5a (all markets marked not to be distributed to) instead returns A70; not
all availability problems are A2. Branches 7a/7b may record A71 and continue.
These differences matter when correlating Exceptions API results and Hub audit.

U 10.4.7 describes an unknown Hub batch but calls its response a batch mismatch;
that wording should not be treated as a confirmed A68 mapping. The more detailed
H flow names A2. This historical terminology is one reason to retain both the
exact source code/message and the step context.

## 4. Can an A3 be caused by an A2 condition?

**Qualified answer: a missing-batch condition can sit behind a pack-not-found
outcome, but these sources do not prove a universal A2-alert-to-A3-alert conversion.**

Three mechanisms must be kept separate:

1. N's shared validation can return A3 directly even with a missing batch when the
   request is not an IMT candidate. This is an explicit conditional path.
2. N 3.1.5.4, exception "Batch Not Found", says to return **Pack Not Found** and a new
   unique pack return code, with the alert raised by the initiating market (review
   page 179). Its state-change counterpart similarly records A99 with reason A2
   and returns a pack-not-found response (Request Intermarket Pack State Change,
   review page 96). This establishes a loss of detail in a returned label, not by
   itself the numeric final alert code in today's REST/Exceptions API.
3. A fulfilling national system uses the same Validate Pack rules. A missing pack
   can therefore lead to A3 without a new IMT search, even if the expected local
   batch data are absent. Treat absent data/distribution as a possible line of
   investigation rather than assuming an isolated missing serial.

To establish whether a real Exceptions API A3 is rooted in a Hub A2, correlate
actual transaction/report references and the original returned code. A human-
readable Pack Not Found label alone is insufficient. N Appendix 4.1 refers the
operation-code catalogue to **EMVS3134 – NMVS Operation Codes**. The current version
of that mapping, and corresponding API contract/release behaviour, remain needed
for a production mapping. Do not fabricate a mapping from the alert label.

## 5. A known batch does not prove that every pack was uploaded

N 3.1.2 expressly permits the packs of one batch to be uploaded in **one or many
bulks**; one bulk only contains packs from one batch. Thus a batch is not necessarily
a single indivisible upload. Its receiving use case describes:

- success with pack-level errors;
- invalid/duplicate serial handling per pack;
- A64 pack-level error details;
- successfully uploaded and failed pack counts in the audit;
- a VALID response that can still include pack-level errors.

See review pages 44 and 46–48. This supports checking the exact serial's inclusion
and acceptance/distribution, not merely the existence of the batch. It does not
establish how often these failures occur operationally. A3 still warrants serious
review when printed/read identifiers agree and technical issues remain unsubstantiated;
it is not itself a finding of counterfeit or of MAH responsibility.

## 6. Source inconsistencies and limits

- U is a historical Draft wrapper with older body version metadata. Some generic
  introduction prose is broader than the specific acceptance criteria. Prefer
  explicit conditions for the reconstruction, and retain the ambiguity.
- N Validate Pack's A3 exception includes an apparent audit-code inconsistency:
  an intermediate audit entry is labelled A68 / Pack Not Found while its return
  is explicitly A3. Do not reproduce this as an A68 business rule.
- The N "Batch Not Found → Pack Not Found" text does not specify today's numeric
  REST operation-code conversion. That remains an open verification item.
- A currently published Snapshot can be later than the alert, and is not proof
  the batch existed or was absent at the event time. Distinguish observed-at-event
  source facts from today's reference checks.
- No conclusion is made here about current R19/R20 implementation conformance.

## 7. Derived Functional Requirements for Operations and Connect

These are proposed SMVS requirements derived from the review, not claims that the
historical sources prescribe our UI or already implemented features.

| ID | Requirement |
| --- | --- |
| FR-INV-CTX-01 | Select investigation family by alert type, refined by exact operation code, API version, attempted operation, source business process, single/bulk context and reviewed IMT role. Unknown context stays unknown. |
| FR-INV-CTX-02 | Retain final source alert/code/message separately from correlated Hub/NMVS audit events and our interpreted explanation. Do not relabel an A3 to A2 based on a current Snapshot absence. |
| FR-INV-CTX-03 | Describe lookup scope only to the extent evidenced: local, intermarket fulfilling response, or not established. Never imply an exhaustive Europe-wide search. |
| FR-INV-CTX-04 | Distinguish missing batch, missing serial, missing distribution and an unestablished result. Correlate A71/distribution evidence where available. |
| FR-INV-CTX-05 | For unresolved A3, compare printed/read product, serial and batch, use exact-batch length/format context if available, obtain a packshot and relevant technical findings. A length match is not an exact-identifier or authenticity result. |
| FR-INV-CTX-06 | Ask the MAH/OBP for inclusion of the exact serial in the relevant upload, pack-level acceptance/errors and market distribution when that evidence is needed. Known batch alone does not complete the check. |
| FR-INV-CTX-07 | Show cause suggestions as hypotheses until evidence supports an NMVO assessment. No automatic A2/A3 resolution based solely on alert category or absence from current reports. |
| FR-INV-CTX-08 | Version the explanation catalogue and keep source references. Preserve a neutral fallback for unresolved or contradictory code mappings. |

Before enabling production rules, cover these cases with source-backed mapping
fixtures: local batch-known/serial-unknown; missing batch/single IMT candidate;
missing batch/bulk non-candidate; known Hub batch/fulfilling serial-unknown;
initiating-only market/A71+A2; all failed distributions/A2; unknown Hub batch;
missing-batch response presented as Pack Not Found with actual final numeric code;
and partial pack upload despite existing batch. Historical expected paths are not
substitutes for release-specific API acceptance fixtures.

## Application to the current proposal

Keep the concise story and source/Intelligence separation. Replace blanket A3/A2
explanations with context-specific messages. A verified local A3 can say:
**The reported serial number was not found in the local NMVS. The batch was known
at the time of the request**, only if both event-time facts are evidenced.
Where the batch finding comes from a later Snapshot, state its date separately.

A confirmed IMT A3 can instead describe the fulfilling-market response. An A2 with
unknown underlying branch should say that the batch lookup/availability failed,
without asserting never uploaded. MAH questions concern causal upload/distribution
evidence; they are not a repetition of the failed lookup. Participant contributions
still belong to a shared case, with NMVO-controlled decision and reviewed visibility.

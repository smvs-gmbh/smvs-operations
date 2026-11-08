# Self-declaration workflow

## Annual cycle

The declaration is for the data year. The invoice is for the following year.
The original Airtable automation computes the declaration year as the current
year minus one. For the 2027 invoice, request 2026 sales and pack counts.

## Fee calculation

The annual fee preview sums the base fee, the quantity fee and the sales-group
fee before VAT. The published annual base fee is CHF 1,500 for every company.
The historical preview uses the imported base fee when available. Confirm
the policy for manual exceptions before using them in invoicing.

| RX quantity group | Pack count | Marginal quantity rate in CHF |
| --- | ---: | ---: |
| VG-001 | 0–50,000 | 0.009 |
| VG-002 | 50,001–1,000,000 | 0.007 |
| VG-003 | 1,000,001–2,000,000 | 0.005 |
| VG-004 | Over 2,000,000 | 0.003 |

Apply each rate to the packs within that band. Round the sum of the bands to
CHF cents using half-up rounding. The code in `app/domain/crm/declaration_fees.py`
contains the supplied eleven sales-group fees. The active Airtable mapping
uses JG-1 for CHF 100,001–3,000,000 and JG-300 for CHF 300,000,001 and above.
The old comment lists conflicting codes. The live Tally form currently starts
at CHF 100,001 and needs an explicit JG-0 option for turnover up to CHF 100,000.
Its visible inputs include packs sold, the turnover band and an optional
purchase order number. Separate name and email inputs were absent when checked.
Verify field and option identifiers against a sample webhook before enabling
intake.

The published page says “over” at both top thresholds while its preceding
bands end at CHF 300,000,000 and 2,000,000 packs. The implemented pack band starts
at 2,000,001, and the live form includes the CHF 300,000,001 sales boundary.

The legacy JavaScript reproduces all 542 available pack amounts for rows with
complete inputs. Decimal half-up differs from it by CHF 0.01 for 26 rows. In 36
rows the historical sales fee was zero despite a fee-bearing group. Preserve
the historical amounts and verify the reason for the zero fees before drawing
conclusions from the differences.

[Published SMVS fee model](https://www.smvs-gmbh.ch/gebuehrenmodell-und-vertraege/gebuehrenmodell) ·
[SMVS self-declaration form](https://forms.smvs-gmbh.ch/r/3xqQBG)

## Invitation and intake design

1. Create one declaration per internal MAH ID and data year. Resolve the MAH's
   SPOCs and review the recipient list. Preserve the addresses approved for the
   invitation.
2. Generate a cryptographically random Auth Code scoped to the declaration.
   Store a digest for lookup and pass the code as a Tally hidden field in the
   invitation URL. The account name and year in the form URL are display
   context. Resolve the declaration using the code.
3. Start by using Make for reviewed delivery. Record the delivery result in
   Operations. The planned SendGrid delivery uses one Mail Send API request per
   declaration, with one personalization per recipient and the same dynamic
   template and form link. This keeps recipient addresses out of each other's
   messages.
4. Verify the Tally webhook signature, identify the configured form and use the
   submission identifier to make retries idempotent. Validate the pack count
   and map the selected sales option to a JG code. Record the submission time,
   the reported count, the selected sales group and the derived quantity group.
5. Capture the provided name, PO number and email on the declaration. Review
   the submitted values before applying any of them to the MAH master record.
   In Airtable a non-empty PO number was copied directly to the MAH.
6. Review the fee and the invoice details before passing them to Bexio.

[Tally hidden fields](https://tally.so/help/hidden-fields) ·
[Tally webhooks and signatures](https://tally.so/help/webhooks)

[SendGrid personalizations](https://www.twilio.com/docs/sendgrid/for-developers/sending-email/personalizations)

## Confirmation after submission

Tally can redirect to a confirmation page after submission. Use a publicly
reachable Operations receipt endpoint once the signed webhook is implemented.
Pass the Tally submission identifier as a correlation value and use a separate
unguessable receipt credential for access to the stored result. The page may
briefly show that processing is pending because the redirect can arrive before
the webhook. After validation and calculation, show the annual fee excluding VAT.
Keep turnover bands, pack counts and amounts out of the redirect URL.

A Tally thank-you page with calculated fields can show an immediate estimate,
but would duplicate the tariff logic and could differ from the centrally
reviewed fee. The Operations receipt is the proposed approach.

[Tally redirect on completion](https://tally.so/help/redirect-on-completion)

## Local test workspace

Start from the project directory:

```sh
.venv/bin/python -m app.portal.test_workspace
```

Open [the test workflow](http://localhost:8013/workflows/self-declarations).
It has synthetic MAHs for two SPOCs, a missing SPOC, indirect billing and a
terminated agreement. Restart the test process to restore the starting dataset.
The test form link stays on the local instance. Create drafts, open the
two-SPOC draft and approve it. Open **Open test form link**, enter 1,000,000
packs and JG-70, then submit. The receipt should show CHF 38,600 excluding VAT.
Repeating the submission for the same invitation returns the original receipt.

Use this local simulation for workflow acceptance. For the live smoke test,
use a controlled test invitation to verify the real Tally submission, signed
webhook and receipt redirect once those endpoints are available.

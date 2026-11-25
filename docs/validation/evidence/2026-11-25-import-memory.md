# Import interruption investigation and correction — 2026-11-25

## Observations

Production Supervisor repeatedly recorded unexpected SIGKILL termination of the
import scheduler during the 03:00–03:27 UTC import window, including every
scheduled SAI/Snapshot attempt on 2026-11-25. Portal workers were also killed on
some previous days. The node has 512 MiB RAM; at investigation, 243 of 256 MiB swap
were in use. Container memory allocation failure counter: 3,036,227. Kernel OOM
messages were not accessible; the precise external kill source cannot be proven
from Supervisor alone. Reproduced excessive memory usage strongly supports memory
exhaustion as the cause.

SAI processing runs remained at extraction. Recent Snapshot staging runs had
succeeded, while product/batch MappingRuns remained running and the selected
publication still pointed to 2026-09-26. Downloads alone did not constitute a
successful end-to-end import.

## Correction and equivalence

- SAI parser uses guarded XML iteration directly from ZIP members. It retains
  extracted records but releases completed XML record subtrees and shares field
  names. DTD/entity/external-reference safeguards and structural validation remain.
- Snapshot staging executes inserts in groups of at most 500; it does not queue
  an ORM object for every source row. Commit responsibility remains with the
  processing orchestrator, including all success markers.
- Product/batch publication reads source datasets in repeatable keyset pages of
  at most 500 rows. Completeness is checked before mapping and after iteration;
  duplicate/source-reference validation remains. Package/batch writes use bounded
  groups within the same publication transaction.

Independent processes parsed the same retained local SAI archive (7,207,606 bytes)
with the original and corrected parser. Results:

| Measure | Original | Corrected |
| --- | ---: | ---: |
| Extracted rows | 94,457 | 94,457 |
| Peak process memory, local macOS measurement | 565.4 MiB | 182.6 MiB |

Both complete extracted outputs, including metadata, dataset names/order/headers
and every original field value, produced SHA-256
`9bfc93a50bab90e6cb51d008eb40af88181d0ddce89850781eabc64b21c98593`.
This is an extraction-equivalence digest, not the archive checksum. Measurement
includes Python/database client overhead; it is not a universal memory ceiling.

Regression verifies 1,001-row package and batch datasets across page boundaries,
repeatable reads, exact evidence, unchanged statistics and idempotency. Injecting
an invalid numeric value after two batch-write groups retains the previous
publication and rolls back all new batch rows. A separate 1,001-row staging test
verifies insert sizes 500/500/1, exact row values/order and full rollback after an
injected error following the final insert.

Local full-suite result: **511 passed** (one existing FastAPI/httpx deprecation
warning). Targeted Ruff checks and `git diff --check` passed.

## Production application

Baseline SHA-256 hashes of all three runtime files matched local HEAD before
application. Original files and a before/after checksum manifest were retained at:

`/var/lib/jelastic/vcs/smvs-operations-current/backups/import-memory-20261125T070134Z`

Only these runtime files were replaced:

- `app/domain/mapping.py`
- `app/integration/sources/sai/parsing.py`
- `app/integration/staging/service.py`

The idle scheduler was stopped gracefully and restarted at 07:01 UTC. No portal,
registration or mail service restart, schema change, unrelated local feature
deployment, or Pilot activation was performed. Historical interrupted executions
and incomplete attempts remain retained as evidence.

Verification used the normal persistent manual-import queue:

| Import | Request | Execution | Result | Completed UTC |
| --- | ---: | ---: | --- | --- |
| SAI | 14 | 352 | Succeeded, first attempt | 2026-11-25 07:02:30 |
| Daily Snapshot | 15 | 353 | Succeeded, first attempt | 2026-11-25 07:04:41 |

ProcessingRuns 412 (SAI) and 413 (Snapshot) succeeded. The Snapshot reused the
already staged canonical result as applicable. MappingRun 10 completed with
5,758 products/source records, 50,987 batches, 8,622 observed product versions,
63,237 SAI packages, 26,043 preparations and 1,364 holders. Product reference
matches: 5,359 matched SAI and 399 without a selected SAI match. The pre-existing
SAI reference was retained deliberately; the new SAI acquisition was not silently
selected for publication.

Both product/batch and participant publications now point to **2026-11-25**,
replacing the previous 2026-09-26 publication. The Snapshot acquisition and
publication completed end to end within approximately 116 seconds.

Scheduler PID 117895 remained unchanged across both imports. Its observed Linux
resident high-water mark was 241,160 KiB (approximately 235.5 MiB). Supervisor
recorded no new unexpected exit during verification. The portal `/health` endpoint
returned `status=ok`, `environment=production` after completion.

This demonstrates recovery on the current dataset, not an unlimited capacity
guarantee. The small server and nearly full swap remain relevant capacity limits;
future scheduled executions should remain visible in normal run history.

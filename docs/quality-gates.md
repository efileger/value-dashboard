# Deployability and quality gates

Assessment: 2026-11-08. Application: one public, read-only Streamlit dashboard and CLI,
with Yahoo Finance access, in-process caches, and a checked-in watchlist. No database,
owned HTTP API, authentication, infrastructure definitions, or container deployment is
present in this repository. Hosting is linked as Streamlit Community Cloud in README;
its deployment configuration is not available in this checkout. GitHub branch metadata
was subsequently read while preparing the PR (see enforcement below).

## Reference and appropriate scope

Use the [Pipeline Reference Architecture](https://beyond.minimumcd.org/docs/reference/pipeline-reference-architecture/)
and its [single-team pattern](https://beyond.minimumcd.org/docs/reference/pipeline-reference-architecture/single-team/).
The reference site's published source was reviewed at
[bdfinst/cd-migration, 8940d5a](https://github.com/bdfinst/cd-migration/blob/8940d5a651eb003473dbe3bc4163424ccd83e807/content/en/docs/reference/pipeline-reference-architecture/_index.md)
because the website itself was blocked by the Dev network policy. Its Hugo configuration
identifies `https://beyond.minimumcd.org/` as the publication URL.

The reference requires cheap checks first, deterministic release gates, contracts at
boundaries, immutable artifacts, and production verification. It explicitly places live
provider integration checks outside the blocking pipeline. Its nine pre-feature gates
are not a requirement to install every tool in every category. Database migrations and
multi-service orchestration are not applicable to this application today.

## Gate mapping

“Added” means implemented in this branch; CI enforcement starts after the branch is
published and required checks are configured. Local passing checks alone are not release evidence.

| Gate | Previous state / gap | Dev and CI tooling / recommendation | Status |
|---|---|---|---|
| Lint and formatting | Ruff lint; no formatting gate | Same pinned Ruff lint and formatter | Added formatting gate and baseline |
| Workflow validity | No workflow syntax gate; live probe had invalid YAML heredoc indentation | Same actionlint 1.7.7 in Dev/CI; optional ShellCheck/Pyflakes subprocess checks disabled consistently | Added; repaired live-probe YAML |
| Types | mypy; many untyped bodies unchecked | Same pinned mypy; type application boundaries incrementally before enabling stricter checks | Existing; strictness remains a gap |
| Secrets | Gitleaks only in CI | Same Gitleaks 8.24.3, staged pre-commit scan plus full-history gate | Added shared installation/check command |
| SAST | CodeQL CI; no cheap local scanner | Bandit in Dev/CI; keep CodeQL as deeper CI analysis | Added Bandit; two B311 exceptions document non-security request jitter |
| Build and reproducibility | Unpinned dependencies; tests in runtime requirements | uv-generated hash-locked runtime/dev requirements, Python 3.11, pip hash verification and dependency consistency check; compile Python | Added locks and compilation; deployable artifact still missing |
| Unit and component tests | pytest and 75% branch-aware coverage | Same pytest, pytest-cov, pytest-timeout, pytest-socket; loopback only in test process | Added isolation/timeouts; fixed accidental live requests and isolated health caches |
| Boundary contracts | Fake ticker sections tested; health and provider verification incomplete | Offline pytest health contract tests for success/throttling/failure, deadlines, cache reuse and forced refresh | Added health consumer contracts; real provider verification still partial |
| SCA | pip-audit resolved unpinned runtime independently | Same pinned pip-audit against exact runtime lock; nonzero error on findings or lookup failure | Added shared audit command |
| Schema migration | No persistent database | No Alembic or database containers needed; revisit when persistence is introduced | Not applicable |
| Acceptance | HTTP shell plus mocked UI calls | Streamlit AppTest executes real page, checks rendered data/action summary and rerun; shared private health smoke | Added; extend actual widget interactions next |
| SBOM and licenses | No inventory or license policy | pip-audit CycloneDX JSON output now; add pip-licenses after agreeing allowed/exception licenses | Added runtime SBOM; license policy remains open |
| Complexity and duplication | No measured budget | Ruff C901 plus Radon for trends; choose budgets from baseline rather than blanket suppression | Proposed |
| Mutation testing | Assertions not measured for fault detection | mutmut on metrics/scoring first; scheduled CI initially, targeted optional Dev run | Proposed |
| Performance and leaks | No latency/memory budgets | pytest-benchmark for computation/cache paths; tracemalloc for repeated fetch/render; promote stable baselines to release gates | Proposed |
| Accessibility / real browser | No rendered WCAG test | Playwright Chromium + axe-core against deterministic demo data; quick Chromium check can run in both, full browser matrix in CI | Proposed; AppTest is not an accessibility test |
| Resilience / cache interactions | Some rate-limit/cache tests; no systematic matrix | Offline pytest for expiry, outage, retries and cache/health interaction; avoid live load on Yahoo | Partial; extend |
| Security integration | No auth or owned API | Test configuration, input handling and diagnostics; add authorization tests if login/private data is introduced | Scoped; do not add irrelevant auth tooling |
| Artifact and promotion | No build-once deployable artifact or promotion workflow | OCI image pinned by digest, GHCR, SBOM, artifact attestation, runtime-only smoke and promote same digest | Missing; next delivery tranche |
| Production verification | No repo-owned production gate or rollback | Release health/synthetic checks, prior-digest rollback, uptime/error/latency SLOs and deploy metadata | Missing; hosting integration needed |
| Branch rules / definitive verdict | README states intended rules, actual rules unverified | Require CI and CodeQL checks on latest merge candidate; prevent bypass/force pushes; one release job depends on all gates | Main requires `lint-and-test` plus dependency/security checks; aggregate gate added; admin bypass remains |

## Shared installation and commands

Supported parity target is Linux x86_64, Python 3.11.5+ in the 3.11 series (the CI/devcontainer runtime).
Soup Sieve 4.0.1 requires this patch-level minimum; lock generation targets Python 3.11.5.
The README's older Python 3.9+ claim is not verified by these locks; supporting other
Python versions requires separate locks and a compatibility matrix. The application
metadata's declared minimum must be reconciled before advertising broader support.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
bash scripts/install-gitleaks.sh
bash scripts/install-actionlint.sh
pre-commit install
bash scripts/check.sh fast
bash scripts/check.sh secrets
bash scripts/check.sh smoke
bash scripts/check.sh audit
```

`fast` runs actionlint, compilation, `pip check`, Ruff, formatting, mypy, Bandit and the complete
coverage-gated suite. Tests have 30-second limits; AppTest has a 15-second script limit.
External network connects from the pytest process are prohibited; loopback supports local
HTTP smoke tests. This is not an OS sandbox for child processes; subprocess tests explicitly
use smoke mode. Never export `SMOKE_TEST` globally: `fast` unsets it and individual
acceptance/smoke tests opt in. The smoke command checks health=200/ok and Streamlit HTML,
logs failures, and terminates only its own child process. Do not run two smoke servers
on port 8501 concurrently.

`secrets` scans committed history; the installed pre-commit hook scans staged changes.
Uncommitted files are not covered by the history scan. Both scans redact findings.
Gitleaks installation checks the release archive against upstream checksums; this is
integrity checking, not independent publisher signature verification.

`audit` needs advisory-service access even though tests are offline. It emits a runtime
CycloneDX SBOM and blocks on vulnerabilities or lookup failure. It is a separate optional
local command (particularly on dependency changes), mandatory in CI. Advisory data changes
over time, so SCA is not perfectly deterministic; keep dependency updates small and never
silently convert a lookup failure to a green result.

On managed hosts with a read-only home cache, set
`export PRE_COMMIT_HOME="$PWD/.venv/.cache/pre-commit"` before invoking pre-commit or committing.
The audit and lock scripts already use writable local caches.

Edit `requirements.in` / `requirements-dev.in`, then run `bash scripts/lock-dependencies.sh`
on Python 3.11.5+ (3.11 series) using the pinned uv version installed with dev requirements. Runtime pins
constrain dev resolution, keeping the application dependencies identical in both.
Commit both `.in` and generated `.txt` files. CI installs locks; it does not upgrade them.
The devcontainer installs the same dev lock and both native scanners. A saved managed Dev environment must also use
this installation command on rebuild; repository changes cannot publish that environment's
settings automatically.

## CI-only work and work outside the release gate

Keep inexpensive checks identical locally and in CI. “CI-only” means central authority,
credentials, or broader execution are needed, not a second implementation of local tests.

- CodeQL: keep centralized deep analysis and SARIF reporting; Bandit does not replace taint analysis.
- Full-history secret scan and authoritative SCA: mandatory CI, optional equivalent local commands.
- Artifact publication, provenance, digest promotion, protected-environment access and rollback:
  CI/CD only; credentials never needed for pre-CI tests.
- Full browser/accessibility matrix, mutation suite, realistic capacity and leak/soak checks:
  scheduled CI initially; targeted subsets remain available in Dev. Stabilize budgets before
  making them required on every release.
- Live Yahoo provider verification: scheduled/post-deploy, alert-only, as the reference specifies.
  The hourly CLI probe (whose invalid YAML is repaired in this branch) checks availability but does not prove every fake payload matches
  Yahoo. Add sanitized structural assertions for the sections used by metrics, timestamps,
  and missing/rate-limited responses. Never make external service uptime a merge gate.
- Production health, synthetic watchlist journeys, SLO monitoring and rollback run during/after
  deployment. Failures trigger rollback or review; they are not ordinary pre-commit tests.

## Next release-control tranche

1. Confirm the actual Streamlit hosting deployment trigger and existing branch protections.
   Auto-deploy from `main` can race post-merge CI. PR checks reduce risk but do not establish
   a single pipeline path to production.
2. Choose hosting that accepts a pipeline-selected immutable artifact (for example GHCR OCI
   images on a managed container host). If keeping Community Cloud, establish its supported
   release controls first; do not claim digest promotion without platform support.
3. Build once, attach lock/SBOM/source SHA/configuration metadata, verify the runtime artifact,
   then promote the same digest only after CI, CodeQL and acceptance all pass. Install no dev
   tools in the deployed runtime.
4. Add production health and deterministic synthetic checks, deployment serialization, a
   previous-known-good reference, tested automatic rollback and an operator runbook.
5. Add Playwright/axe, scoring mutation tests and performance budgets in small independently
   reviewable batches. No database/schema or language race-sanitizer gate is justified today;
   Python cache concurrency still deserves behavior tests if sessions share mutable state.

The fast gates increase confidence, not a guarantee of deployability. Until artifact
promotion, hosting controls and rollback are implemented and exercised, this project does
not fully meet the reference architecture's production delivery intent.

## Validation of this integration

Dev: 52 tests passed with 77.39% coverage, including real Streamlit page execution
and six offline HTTP-boundary cases. Ruff lint/format, mypy, Bandit, actionlint,
pre-commit configuration validation, full-history Gitleaks, and private smoke passed.
The runtime lock also installed in a separate runtime-only virtual environment and
passed the health/homepage smoke. The repaired live-probe workflow was exercised with
stubbed data through report and summary generation; no webhook was sent. SCA found
no known vulnerabilities and generated a CycloneDX inventory of 43 runtime components.
GitHub CI has not run these changes until a PR is opened.

## CI enforcement

The `CI` workflow independently installs hash-locked tools and invokes the same shared
commands as Dev. The existing required `lint-and-test` status is an aggregate: it runs
with `if: always()` and fails unless fast checks, dependency audit, secret scan and the
runtime-only Dev smoke all succeed. Failure, cancellation or skipped prerequisites do
not turn the aggregate green. The local pre-commit hook is convenience, not CI evidence.

GitHub main-branch metadata confirms protection requires `lint-and-test`,
`Dependency security audit`, `gitleaks` and `CodeQL` with their configured app identities.
Its reported enforcement level is `non_admins`: administrators can bypass checks. No
additional rulesets were returned. The integration cannot read/change the full protection
configuration (administration permission denied); enabling administrator enforcement and
verifying review/strict-up-to-date settings remain repository-owner configuration tasks.

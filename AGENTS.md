# Agent Guidelines for Value Dashboard

This repository follows trunk-based development practices with a minimumCD mindset.

## Delivery Behaviors
- Application pipeline is the only path to production; never bypass checks or force-push to `main`.
- Build on every commit in short-lived branches cut from `main`; merge only through reviewed PRs with a green pipeline.
- Stop the line when CI fails and fix forward before adding new work. Surface failures with clear context.
- Prefer evolutionary coding in small batches with feature flags when behavior changes are risky.
- Keep branch protections (required checks, no force-push, no branch deletion) aligned with the pipeline.

## Quality, Testing, and Safety Nets
- Maintain deterministic automated tests (unit/functional/integration/smoke) and run them in CI; add resilience/performance/security checks when relevant.
- Use static analysis (e.g., Ruff) and compliance/security scans as quality gates.
- Favor acceptance or behavior-driven tests for user-facing features; practice exploratory testing for UI changes.
- Treat CI as the production readiness indicator—if it is red, the release is blocked.

## Artifacts, Configuration, and Environments
- Create immutable artifacts per build with automated versioning; publish to an artifact repository when available.
- Package application configuration alongside artifacts; manage secrets via environment variables or a secret store (never commit secrets).
- Keep production-like test environments; prefer ephemeral environments for branches when possible.
- Enable on-demand rollback by keeping deployments reversible and configuration versioned.
- Preserve dependency lock-in and monitor supply chain updates (dependency management).

## Architecture and Ownership
- Keep the system modular with clear component ownership; document APIs and contracts.
- Track cycle time and favor a unified team backlog with prioritized features.
- Use telemetry/observability and monitoring/alerting to detect regressions quickly; ensure logging infrastructure supports debugging.

## Implementation Preferences
- Favor loosely coupled modules with clear seams (data access, computation, and UI/presentation) so changes in one area do not ripple unnecessarily through the others.

## Additional Expectations
- Update documentation (README, runbooks) when delivery or operational processes change.
- Guard against brittle dependencies by handling API changes defensively and surfacing clear user-facing errors.
- Keep instructions in this file current when adopting new CD practices or tooling.

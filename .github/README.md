# Repository automation

Phase 1 adds `.github/workflows/ci.yml` with non-production backend and Flutter checks. The workflow does not deploy, publish artifacts, access production credentials, or enable branch protection, secret-scanning services, or private vulnerability reporting.

## Checks

- Backend dependencies are installed from `backend/requirements.lock` with hashes.
- Backend tests run with synthetic data and an isolated temporary SQLite database.
- Flutter 3.44.8 resolves `mobile/pubspec.lock` with `--enforce-lockfile`.
- Flutter analyzer and tests run from `mobile/`.

The workflow is a reproducibility check, not a production-readiness or security-audit claim. Android release signing, deployment, dependency/security scanning, authorization regression coverage, and platform release checks require separate implementation and approval.

## Security boundaries

- Workflow permissions are read-only.
- Untrusted pull requests must not receive privileged credentials.
- Third-party actions are pinned to reviewed immutable commit SHAs.
- Logs must not contain credentials, private report content, evidence, or secret-bearing configuration.
- No workflow publishes APKs or deploys services.
- Establish a real private disclosure process before making any claim that one exists; see `../SECURITY.md`.

Source of truth: `../docs/implementation-blueprint.md`.

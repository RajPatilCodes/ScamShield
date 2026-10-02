# Planned repository automation

No GitHub Actions workflow, deployment, branch protection, secret-scanning service, or private vulnerability-reporting configuration has been established by Phase 0. This file does not enable any GitHub setting.

## Planned after the development baseline is verified

- Backend lint/test checks in an isolated synthetic-data environment.
- Flutter analysis and tests with an explicitly supported toolchain.
- Secret detection and dependency/security checks with reviewed configuration.
- API-contract and authorization regression checks.
- Platform build verification when signing and runner requirements are approved.

Do not add placeholder workflows that imply tests pass. Do not enable deployment or publish artifacts automatically as part of repository establishment.

## Security boundaries

- Untrusted pull requests must not receive privileged credentials.
- Minimize workflow permissions and pin third-party actions to reviewed immutable revisions.
- Never print credentials, private report contents, evidence, or secret-bearing configuration.
- Production environments, signing, approvals, and release automation require separate approval.
- Establish a real private disclosure process before making any claim that one exists; see `../SECURITY.md`.

Source of truth: `../docs/implementation-blueprint.md`.

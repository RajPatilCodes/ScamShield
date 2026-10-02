# Phase 0 repository baseline

## Authorized scope

Establish one local Git repository, add protection/documentation, review and scan candidates, and stage the preserved baseline. **Do not commit, push, start Phase 1, or change application functionality.**

Intended remote: `https://github.com/RajPatilCodes/ScamShield.git`.

The owner states that the GitHub repository is intentionally empty. Phase 0 does not contact GitHub or independently verify remote state. Adding `origin` is local configuration only.

## Initial inspection

- The existing workspace contains the actual Flutter project in `mobile/` and FastAPI project in `backend/`.
- No `.git` directory/file/link was found within the workspace before setup. Neither application was a separate repository.
- Previous root/mobile/backend status, branch, remote, and log checks all reported that no repository existed.
- No application files need to move. A local directory name different from the GitHub repository name is acceptable.
- Existing tests remain in `mobile/test/` and `backend/tests/`. Root `tests/` currently documents future cross-system tests only.
- No usable historical diff is available to attribute every change to the Windows session. Preserve all current useful work, not just the five handoff paths.

## Pre-change preservation fingerprints

The following SHA-256 values matched the earlier read-only inspection before Phase 0 file creation:

| File | SHA-256 |
| --- | --- |
| `README.md` | `b1980546d0c36bda7bec209b1289451a957f898fddcc8c6352db79c0c40241ba` |
| `mobile/lib/services/api_service.dart` | `e3606f845f58e1321c24e194df097ae458fe6765922bb31e7aad2c51f1cdb0db` |
| `mobile/android/gradle.properties` | `67d477cb08ad088e50b40b01cd6bf76149d70f74b194c0331c9e8882a7c822d8` |
| `mobile/android/app/src/main/AndroidManifest.xml` | `6d18f878d0406c7ceda46b560e9c05754581683956745b56760955badeadf466` |
| `mobile/android/app/src/main/res/xml/network_security_config.xml` | `4418a841a7c4a426a5b97fa1e2356c7fcffd93dc184be429e5cb673c50f47edc` |

An additional pre-change inventory covers 65 existing source/configuration/test/asset files. Its aggregate SHA-256 is `3c97344a843bd1512612216a873978d51b083d24d5177b9dfb2152746f8a5269`.

Inventory construction: include existing files under `backend/app`, `backend/tests`, `mobile/lib`, `mobile/test`, and `mobile/android`, plus root README/Compose, backend Dockerfile/requirements, and mobile README/pubspec/lockfile/analyzer configuration/metadata/ignore file. Exclude local machine properties, signing/environment files, IDE metadata, logs, bytecode, and generated cache/build directories. Sort paths and hash the UTF-8 manifest of each content SHA-256, two spaces, relative POSIX path, and newline. The Android wrapper and generated plugin source are protected locally even where existing ignore rules exclude them from staging.

## New baseline files

- `.gitignore`
- `backend/.dockerignore`
- `docs/implementation-blueprint.md`
- `docs/current-state.md`
- `docs/repository-baseline.md`
- `tests/README.md`
- `.github/README.md`
- `SECURITY.md`
- `PRIVACY.md`

No existing README, Compose file, application source, component test, or Android configuration is to be edited. The security/privacy documents explicitly distinguish existing behavior from planned controls; they are not production policies or guarantees.

## Git setup and preservation policy

Initialize `main` at the workspace root. Set only local `core.autocrlf=false` and `core.fileMode=false` to avoid automatic line-ending conversion and unreliable Windows-mounted executable-bit churn. Do not change global configuration or invent commit identity.

Keep existing nested ignore rules. The current Android template ignores wrapper scripts/JAR and generated plugin registration; do not force-add them. Verify Flutter build regeneration/reproducibility in Phase 1 before changing that policy.

Exclude environment files (including the unreviewed example), databases/sidecars, signing material, machine configuration, caches, build artifacts, private runtime data, and agent/tool state. These exclusions preserve local files; they do not delete anything or implement application data deletion.

## Candidate review and secret checking

Only reviewed source, configuration, tests, authored assets, dependency declarations, and the new baseline documents may enter the index. Never use `git add .` or force-add ignored paths.

Check for an already installed suitable secret scanner. Do not install one automatically. If unavailable, use a read-only static fallback over exact candidate content: check forbidden paths, links/file types, private-key and provider-token formats, credential-bearing URLs, sensitive assignments, structured configuration, and high-entropy candidates. Print locations and classifications, not secret values. Manually review findings and rescan staged content against the reviewed bytes.

Static pattern checks cannot prove that a repository is secret-free, especially for novel formats, obfuscation, binary metadata, or unknown real-world credentials. Existing synthetic test values and known development defaults must be distinguished from genuine credentials without broad scan exclusions. Development defaults remain release blockers, not production secrets to use.

No application test/build execution or credential-dependent external request belongs to Phase 0.

## Acceptance gate before stopping

1. One root repository, initial branch `main`, correct local `origin`.
2. Sensitive/generated ignore probes succeed, including nonexistent representative secret paths.
3. Exact candidate set reviewed; no database, environment, build, signing, machine, or agent file staged.
4. Secret-check findings reviewed with limitations stated.
5. Index contains only approved additions; no unexpected staged file or deletion.
6. Staged source bytes match the worktree; original preservation fingerprints still match.
7. Inspect cached name/status, statistics, whitespace checks, and final status.
8. Record warnings rather than formatting preserved source to silence them.
9. No commits, pushes, application changes, dependency installs, or Phase 1 work.

Application validation, a dedicated secret scanner if absent, remote verification, commit identity, commit approval, and push approval remain separate follow-up work.

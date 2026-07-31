# Release Process

## Release candidate

1. Create a short-lived branch from `develop` (or the repository's configured
   integration branch).
2. Update the package version and release notes when a versioned release is intended.
3. Run the CI-equivalent non-live validation in a clean Python 3.12 environment.
4. Confirm `original_notebook.ipynb` matches its recorded checksum and review
   `FINAL_PARITY_REPORT.md` plus all accepted differences.
5. Open a pull request; require the CI workflow and human review before merge.
6. Merge to `develop`, perform staging validation when a staging target exists, then
   open a release pull request to `main`.

## Release and verification

1. Tag the approved `main` commit using the repository's chosen semantic version.
2. Build from that exact commit; do not reuse unverified local artifacts.
3. Inject `OPENAI_API_KEY` through the hosting secret manager, never the repository.
4. Deploy only after the manual controls in `CI_CD.md` are configured.
5. Verify the health endpoint/startup, project setup, a non-sensitive mocked or test
   survey workflow, downloads, and absence of secrets/survey content in logs.
6. Record the deployed commit/tag, environment, verifier, and time.

No tag, hosted deployment, branch protection, or environment configuration has been
performed or claimed by this implementation.

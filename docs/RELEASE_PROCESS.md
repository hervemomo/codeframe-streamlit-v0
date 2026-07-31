# Release Process

Finalize during Phase 5.

## Proposed flow

1. Create a short-lived feature branch from the integration branch.
2. Implement a coherent change and run proportional validation.
3. Open a pull request and satisfy required CI checks.
4. Merge to the integration branch and deploy to development/staging when configured.
5. Open a reviewed release pull request to the production branch.
6. Obtain required approvals.
7. Deploy from the approved branch, tag, or release.
8. Perform post-deployment smoke validation.
9. Roll back or forward-fix if validation fails.

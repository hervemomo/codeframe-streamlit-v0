# Rollback Plan

Finalize after the deployment platform is selected.

## Minimum rollback requirements

- Identify the last known-good release or commit.
- Preserve current logs and failure evidence without exposing sensitive data.
- Restore the previous application artifact or redeploy the prior commit.
- Verify startup and a safe smoke workflow.
- Record the incident and corrective action.

Do not claim provider-specific rollback automation until it is implemented and verified.

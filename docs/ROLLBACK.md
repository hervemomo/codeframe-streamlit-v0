# Rollback Plan

## Trigger

Rollback when startup, authentication, data isolation, coding correctness, downloads,
or security checks fail after release and a safe forward fix cannot be verified
immediately.

## Provider-neutral procedure

1. Stop new user sessions or place the application in maintenance mode using the
   selected provider's documented control.
2. Preserve failure evidence and configuration metadata without copying credentials or
   survey response content into tickets or logs.
3. Identify the last known-good immutable commit/tag and its previously verified
   artifact.
4. Restore that artifact or redeploy that exact commit with the prior compatible
   configuration and secrets.
5. Run the local health/startup smoke check and a non-sensitive workflow/download
   check.
6. Confirm no incompatible persisted state requires migration; this application keeps
   workflow state session-local and writes only explicit report files.
7. Record the incident, rollback target, verifier, and corrective action.

Provider-specific rollback automation is not claimed because no deployment platform
has been selected. Before production launch, operations must document the exact
provider command, retention behavior, recovery time objective, owner, and escalation
path.

# CI/CD Plan

This is an initial contract. Codex must align it with the repository and hosting provider.

## Continuous integration

CI should run on pull requests and protected integration/production branches and include, as applicable:

- clean installation;
- formatting verification;
- linting;
- static type checking;
- targeted or full non-live tests according to workflow scope;
- coverage enforcement;
- security checks;
- dependency audit;
- package/import validation;
- Streamlit startup smoke validation.

## Continuous delivery

Recommended flow:

```text
feature branch
→ pull request
→ required CI checks
→ merge to integration branch
→ development/staging deployment
→ release pull request
→ protected production deployment
```

## Manual repository settings

Codex must not claim these are configured unless verified:

- branch protection;
- required status checks;
- GitHub environments;
- reviewers and approvals;
- repository secrets;
- hosting credentials.

## Test policy

- Use targeted tests during implementation.
- Use affected-component tests when shared contracts change.
- Use phase-gate checks at each phase boundary.
- Run the complete non-live validation once before final completion.

# Workflow Placeholders

Codex must create and validate the actual workflows during implementation after inspecting the repository's package manager, Python versions, commands, and deployment target.

Expected files by final completion:

- `ci.yml`
- `deploy.yml`
- optional `live-smoke.yml`

Do not create a fake deployment workflow before a hosting target and required secrets are known. Provider-neutral build and validation steps may be created earlier.

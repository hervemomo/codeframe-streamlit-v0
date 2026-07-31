# CI/CD

## Continuous integration

`.github/workflows/ci.yml` runs for pull requests and pushes targeting `develop`
or `main`, plus manual dispatch. It uses Python 3.12 and:

1. installs `.[dev]` from authoritative `pyproject.toml`;
2. verifies the immutable notebook SHA-256;
3. rejects Streamlit imports in `src/codeframe`;
4. checks Ruff formatting and lint;
5. runs strict mypy;
6. runs the non-live pytest suite with an 80% coverage gate;
7. runs Bandit and pip-audit;
8. builds the package and validates its import;
9. starts the final Streamlit application headlessly and polls its local health
   endpoint.

Default tests never call live APIs. The `live_api` marker is opt-in and excluded
from CI. Streamlit `AppTest` coverage verifies safe prerequisites, both explicit
coding actions with mocked services, cancelled refinement freshness, and results
rendering.

## Dependency authority

`pyproject.toml` defines runtime and development dependencies. The retained
`requirements.txt` contains only `.` for deployment platforms that require that
filename, so it cannot silently diverge.

## Continuous delivery

No deployment workflow exists because no hosting target, credentials, data-retention
policy, or environment policy was selected. Repository CI and local launch are ready;
provider configuration is deliberately a manual product/operations decision.

## Manual repository settings

The following are not verified or configured by files in this repository:

- branch protection and required checks;
- reviewer rules;
- GitHub environments;
- repository/hosting secrets;
- deployment target and credentials;
- survey-data residency, retention, and access controls;
- hosted application authentication and authorization;
- post-deployment health monitoring and alerting.

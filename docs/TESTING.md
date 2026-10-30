# Testing

Run `pytest -q` from `backend` after installing requirements. The suite uses FastAPI's test client against the local app and covers the primary safety, mission, diagnostics, audit, reset, and readiness flows.

The frontend package includes the Vitest command and can be extended with React Testing Library. Browser E2E tests are not bundled because no browser test dependency is required for the offline default install. Test execution results are recorded in the delivery report, not assumed here.

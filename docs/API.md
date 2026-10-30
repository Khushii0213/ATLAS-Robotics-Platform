# API

Interactive OpenAPI documentation is served at `/docs`.

| Group | Endpoints |
|---|---|
| Health | `GET /api/health` |
| Fleet | `GET /api/robots`, `GET /api/robots/{id}`, `GET /api/robots/{id}/telemetry` |
| Teleoperation | `POST /api/robots/{id}/commands`, `POST /api/robots/{id}/stop` |
| Missions | `GET/POST /api/missions`, `GET /api/missions/{id}`, `GET /preflight`, `POST /start`, `/pause`, `/resume`, `/cancel` |
| Diagnostics | `GET /api/alerts`, `POST /api/alerts/{id}/resolve`, `POST /api/simulation/faults` |
| Operations | `GET /api/logs`, `/logs/export`, `/analytics`, `/deployments`, `/customers`, `/support`, `/audit` |
| Simulation | `POST /api/simulation/reset`, `WS /ws/fleet` |

`POST /api/robots/{id}/commands` accepts `{ "command": "forward|backward|left|right|stop|estop|clear_estop", "speed": 0..1 }`. The backend rejects movement while offline or emergency-stopped, and records every accepted safety/teleop action in the audit stream.

Mission preflight reports individual checks and clear blocking reasons; Start returns HTTP 409 if it does not pass.

# Design decisions

1. **Deterministic in-memory seed over a durable demo database:** resettable, reviewable interview scenario and no local personal data artifact. The data boundary is intentionally narrow for a repository upgrade.
2. **Server validates every command:** keyboard and on-screen controls call the same endpoint; UI cannot bypass safety policy.
3. **Simulation-only is explicit:** camera panel and top-level state identify simulation mode. No ROS dependency is included.
4. **Cause labels are suggestions:** diagnostic probable causes are written as inference, not root-cause certainty.
5. **Dense aerospace visual language:** compact panels, tactical grid, monospaced telemetry, thin boundaries, and restrained color encode operational states.

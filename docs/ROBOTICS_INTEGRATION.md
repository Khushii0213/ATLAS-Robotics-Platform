# Robotics integration design

ATLAS currently ships only the `SimulationAdapter` behaviour embedded in the FastAPI service. A future adapter boundary would expose `send_command(robot_id, command)`, `telemetry()`, `health()`, and mission/navigation goal methods. The API remains the safety policy enforcement point.

An optional `rclpy` adapter would subscribe to `/odom`, `/scan`, `/imu`, `/battery_state`, and `/tf`; publish velocity only to `/cmd_vel`; and translate health status into ATLAS telemetry. It must be separately configured with an explicit allowlist and authenticated command gateway. It is not installed or enabled by this project. Physical motion is therefore impossible with the default setup.

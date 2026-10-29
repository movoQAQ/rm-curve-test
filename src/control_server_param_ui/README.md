# control_server_param_ui

A zero-dependency ROS2 parameter tuning UI for `/control_server`.

It reads all parameters by:

1. `ros2 param list /control_server`
2. `ros2 param get /control_server <param_name>` for every parameter

Then you can edit values in the UI and send updates with:

- `ros2 param set /control_server <param_name> <value>`

## Run

Use a terminal where ROS2 environment is already sourced and `/control_server` is running:

```bash
python3 control_server_param_ui.py
```

## Features

- Refresh and load all parameters from target node
- Edit one parameter and set immediately
- Batch set all changed parameters
- Show per-parameter status and global status

## Notes

- Default node is `/control_server`, but you can change it in the UI.
- If node is offline, refresh will fail with `Node not found`.
- Values are passed directly to `ros2 param set`, following ROS2 CLI YAML parsing rules.

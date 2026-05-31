# Camera2D

Camera2D defines viewport position, offset, zoom, and optional movement limits.

| Function | Description |
| --- | --- |
| __init__() | Initializes camera offset, zoom, and optional viewport limits. |

| Property | Description |
| --- | --- |
| position | Local camera position relative to the parent node. |
| offset | Screen-space offset applied when rendering from this camera. |
| current | Marks the camera as the active camera. |
| zoom | Camera zoom factor used by the renderer. |
| limit_min | Minimum world-space viewport edge. -1 disables that axis. |
| limit_max | Maximum world-space viewport edge. -1 disables that axis. |
| global_position | Raw world-space camera position (not clamped). |

# Camera2D

Camera2D defines viewport position, offset, zoom, and optional movement limits.

| Function | Description |
| --- | --- |
| __init__() | Initializes camera offset, zoom, and optional global limits. |
| global_position (property getter) | Returns camera world position after applying clamp limits. |
| global_position (property setter) | Writes camera world position with clamp and parent conversion. |

| Property | Description |
| --- | --- |
| position | Local camera position relative to the parent node. |
| offset | Screen-space offset applied when rendering from this camera. |
| current | Marks the camera as the active camera. |
| zoom | Camera zoom factor used by the renderer. |
| limit_min | Minimum world-space camera position. |
| limit_max | Maximum world-space camera position. |
| global_position | Clamped world-space camera position. |

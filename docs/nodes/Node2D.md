# Node2D

Node2D extends Node with transform state in 2D space.

| Function | Description |
| --- | --- |
| __init__() | Initializes position, rotation, and z_index. |
| global_position (property getter) | Computes world position from parent hierarchy. |
| global_position (property setter) | Writes local position from requested world position. |

| Property | Description |
| --- | --- |
| position | Local 2D position relative to the parent node. |
| rotation | Local rotation value stored on the node. |
| z_index | Render ordering index used by the renderer. |
| global_position | World-space position resolved through the parent hierarchy. |

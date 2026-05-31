# Node2D

Node2D extends Node with transform state in 2D space.

| Function | Description |
| --- | --- |
| __init__() | Initializes position, rotation, z_index, and visibility. |
| global_position (property getter) | Computes world position from parent hierarchy. |
| global_position (property setter) | Writes local position from requested world position. |
| global_visible (property getter) | Resolves effective visibility through the parent hierarchy. |

| Property | Description |
| --- | --- |
| position | Local 2D position relative to the parent node. |
| rotation | Local rotation value stored on the node. |
| z_index | Render ordering index used by the renderer. |
| visible | Local visibility toggle for this node. |
| global_position | World-space position resolved through the parent hierarchy. |
| global_visible | Effective visibility inherited from parent Node2D nodes. |

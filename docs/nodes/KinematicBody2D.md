# KinematicBody2D

KinematicBody2D represents a script-driven body with velocity helpers.

| Function | Description |
| --- | --- |
| __init__() | Initializes kinematic velocity field. |
| move_and_slide() | Moves body by current velocity in global space. |

| Property | Description |
| --- | --- |
| position | Local position inherited from Node2D. |
| rotation | Local rotation inherited from Node2D. |
| z_index | Render ordering inherited from Node2D. |
| velocity | Linear velocity applied by move_and_slide(). |

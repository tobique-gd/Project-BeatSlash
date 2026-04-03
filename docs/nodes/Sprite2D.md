# Sprite2D

Sprite2D renders a texture resource in world space.

| Function | Description |
| --- | --- |
| __init__() | Initializes sprite transform offsets and texture slot. |
| save_data() | Saves sprite fields and texture resource reference. |
| load_data(data) | Loads sprite fields and texture resource reference. |
| texture (property getter) | Returns current texture resource. |
| texture (property setter) | Accepts texture resource or path and resolves resource binding. |
| image (property getter) | Returns renderable surface with horizontal and vertical flip applied. |

| Property | Description |
| --- | --- |
| position | Local sprite position relative to the parent node. |
| rotation | Local rotation value inherited from Node2D. |
| z_index | Sprite render ordering inherited from Node2D. |
| flip_h | Flips the sprite horizontally when rendering. |
| flip_v | Flips the sprite vertically when rendering. |
| offset | Pixel offset applied during rendering. |
| texture | Bound texture resource or resource path. |
| image | Render-ready surface after texture lookup and flipping. |

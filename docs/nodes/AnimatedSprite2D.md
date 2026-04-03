# AnimatedSprite2D

AnimatedSprite2D extends Sprite2D with frame-based animation resources.

| Function | Description |
| --- | --- |
| __init__() | Initializes animation list and active animation state. |
| current_animation (property getter) | Returns active animation resource. |
| current_animation (property setter) | Assigns active animation from resource or path. |
| save_data() | Saves animation playback state in addition to sprite data. |
| load_data(data) | Restores animation playback state and active animation. |
| add_animation(animation) | Adds animation resource to animation list. |
| play(name) | Activates animation by name and resets playback state. |
| _update(delta) | Advances active animation in runtime mode. |
| editor_update(delta) | Advances active animation in editor mode. |
| image (property getter) | Returns current animation frame surface. |

| Property | Description |
| --- | --- |
| animations | List of animation resources available to the sprite. |
| current_animation | Currently active animation resource. |
| flip_h | Flips the current frame horizontally when rendering. |
| flip_v | Flips the current frame vertically when rendering. |
| offset | Pixel offset applied during rendering. |
| texture | Inherited texture slot from Sprite2D; not used by animated playback. |
| image | Render-ready surface for the current animation frame. |

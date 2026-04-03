# AudioPlayer

AudioPlayer owns an AudioStream resource and playback controls.

| Function | Description |
| --- | --- |
| __init__() | Initializes audio resource slot and volume. |
| save_data() | Saves node fields and audio resource reference. |
| load_data(data) | Loads node fields and audio resource reference. |
| play() | Plays currently assigned sound resource. |
| volume (property getter) | Returns playback volume value. |
| volume (property setter) | Sets volume and applies it to bound sound resource. |
| audio (property getter) | Returns bound audio resource. |
| audio (property setter) | Assigns audio from resource or path and updates volume on load. |
| on_exit() | Stops active sound before leaving scene tree. |

| Property | Description |
| --- | --- |
| volume | Playback volume applied to the bound audio resource. |
| audio | Bound audio stream resource or resource path. |

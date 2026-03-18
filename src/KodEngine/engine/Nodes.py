from . import Resources
import pygame
import os


class Node:
    def __init__(self) -> None:
        self.name = self.__class__.__name__
        self._children = []
        self._parent: 'Node | None' = None
        self._script_resource = None
        self.runtime_script: object | None = None
        self.script = None
        self._queued_for_deletion = False

    def _on_enter(self):
        for child in getattr(self, "_children", []):
            try:
                child._on_enter()
            except Exception:
                pass

    def on_exit(self):
        for child in getattr(self, "_children", []):
            try:
                child.on_exit()
            except Exception:
                pass

    def add_child(self, _node):
        self._children.append(_node)
        _node._parent = self
    
    def remove_child(self, _node):
        if _node in self._children:
            _node._parent = None
            self._children.remove(_node)
    
    def queue_free(self):
        self._queued_for_deletion = True

    def get_node(self, _path_to_child: str):
        parts = _path_to_child.split("/")
        current_node = self
        for part in parts:
            found = None
            for child in current_node._children:
                if child.name == part:
                    found = child
                    break
            if found is None:
                return None
            current_node = found
        return current_node
    
    def get_child(self, index: int):
        if index < 0 or index >= len(self._children):
            return None
        return self._children[index]

    def get_nodes_by_type(self, node_type):
        found_nodes = []
        for child in self._children:
            if isinstance(child, node_type):
                found_nodes.append(child)

            found = child.get_nodes_by_type(node_type)
            if found is not None:
                found_nodes.extend(found)

        return found_nodes

    def set_script(self, module_name: str):
        self.script = module_name

    def reparent_to(self, new_parent: 'Node'):
        if self._parent is not None:
            self._parent.remove_child(self)
        new_parent.add_child(self)

    @property
    def script(self):
        return self._script_resource

    @script.setter
    def script(self, value):
        if isinstance(value, Resources.Script):
            self._script_resource = value
        elif isinstance(value, str):
            self._script_resource = Resources.Script(resource_path=value)
        elif value is None:
            self._script_resource = None
        else:
            self._script_resource = None

        script_path = None
        if self._script_resource is not None:
            script_path = self._script_resource.resource_path or self._script_resource.script_path

        if script_path:
            try:
                self.runtime_script = Resources.load_script(script_path, self)
            except Exception:
                self.runtime_script = None
        else:
            self.runtime_script = None

    
    def _update(self, _delta):
        pass

    def editor_update(self, delta):
        pass

    def save_data(self) -> dict:
        data = {}
        for name, value in vars(self).items():
            if name.startswith("_"):
                continue
            if name == "script" or name == "runtime_script":
                continue
            if callable(value):
                continue
            data[name] = value
        
        if self._script_resource:
            data["script"] = self._script_resource
            
        return data

    def load_data(self, data: dict):
        for name, value in data.items():
            if hasattr(self, name):
                try:
                    setattr(self, name, value)
                except Exception as e:
                    print(f"Error setting {name} on {self.name}: {e}")

class Node2D(Node):
    def __init__(self) -> None:
        super().__init__()
        self.position: tuple[float, float] = (0, 0)
        self.rotation: tuple[float, float] = (0, 0)
        self.z_index = 0

    @property
    def global_position(self):
        if self._parent is None:
            return self.position
        if isinstance(self._parent, Node2D):
            p = self._parent.global_position
            return (self.position[0] + p[0], self.position[1] + p[1])
        return self.position


    @global_position.setter
    def global_position(self, value: tuple[float, float]) -> None:
        if self._parent is None:
            self.position = value
        elif isinstance(self._parent, Node2D):
            parent_global = self._parent.global_position
            self.position = (value[0] - parent_global[0], value[1] - parent_global[1])
        else:
            self.position = value
    
class CollisionShape2D(Node2D):
    def __init__(self) -> None:
        super().__init__()

class RectangleCollisionShape2D(CollisionShape2D):
    def __init__(self) -> None:
        super().__init__()
        self.size = (32, 32)

class Sprite2D(Node2D):
    def __init__(self) -> None:
        super().__init__()

        self.flip_h, self.flip_v = False, False
        self._texture_resource = None
        self.position = (0,0)
        self.offset = (0,0)
    
    def save_data(self) -> dict:
        data = super().save_data()
        if self._texture_resource:
            data["texture"] = self._texture_resource
        return data

    def load_data(self, data: dict):
        super().load_data(data)
        if "texture" in data:
            self.texture = data["texture"]

    @property
    def texture(self):
        return self._texture_resource

    @texture.setter
    def texture(self, value):
        from .Resources import Texture2D

        if isinstance(value, Texture2D):
            self._texture_resource = value
        elif isinstance(value, str):
             from .ResourceServer import ResourceLoader
             try:
                 res = ResourceLoader.load(value)
                 if isinstance(res, Texture2D):
                     self._texture_resource = res
                 else:
                     self._texture_resource = Texture2D(resource_path=value)
             except Exception:
                 self._texture_resource = None
        else:
             self._texture_resource = None

    @property
    def image(self):
         if self._texture_resource:
             surf = self._texture_resource.get_texture()
             if surf:
                return pygame.transform.flip(surf, self.flip_h, self.flip_v)
         return None


class AnimatedSprite2D(Sprite2D):
    def __init__(self):
        super().__init__()
        self.animations: list[Resources.SpriteAnimation] = []
        self.name = "AnimatedSprite2D"
        
        self._current_animation: Resources.SpriteAnimation | None = None

    @property
    def current_animation(self):
        return self._current_animation

    @current_animation.setter
    def current_animation(self, value):
        if isinstance(value, Resources.SpriteAnimation):
            self._current_animation = value
        elif isinstance(value, str):
             from .ResourceServer import ResourceLoader
             try:
                 res = ResourceLoader.load(value)
                 if isinstance(res, Resources.SpriteAnimation):
                     self._current_animation = res
                 else:
                     self._current_animation = Resources.SpriteAnimation.from_path(value)
             except Exception:
                 self._current_animation = None
        else:
             self._current_animation = None

    def save_data(self) -> dict:
        data = super().save_data()
        if self.current_animation:
             data["current_animation"] = {
                 "name": self.current_animation.name,
                 "current_frame": self.current_animation.current_frame,
                 "time_accumulator": self.current_animation.time_accumulator
             }
        return data

    def load_data(self, data: dict):
        data_copy = data.copy()
        curr_anim_data = data_copy.pop("current_animation", None)
        
        super().load_data(data_copy)
        
        if curr_anim_data and isinstance(curr_anim_data, dict):
            name = curr_anim_data.get("name")
            if name:
                self.play(name)
                if self.current_animation:
                    self.current_animation.current_frame = int(curr_anim_data.get("current_frame", 0))
                    self.current_animation.time_accumulator = float(curr_anim_data.get("time_accumulator", 0))


    def add_animation(self, animation: Resources.SpriteAnimation):
        self.animations.append(animation)

    def play(self, name: str):
        if self._current_animation and name == self._current_animation.name:
            return

        for anim in self.animations:
            if anim.name == name:
                self._current_animation = anim
                anim.current_frame = 0
                anim.time_accumulator = 0
                break

    def _update(self, delta: float):
        if self.current_animation:
            self.current_animation.update(delta)
    
    def editor_update(self, delta):
        if self.current_animation:
            self.current_animation.update(delta)

    @property
    def image(self):
        if self.current_animation:
            frames = getattr(self.current_animation, "frames_surfaces", None)
            frame_index = getattr(self.current_animation, "current_frame", 0)
            if not frames:
                return None
            if frame_index < 0 or frame_index >= len(frames):
                return None
            return pygame.transform.flip(frames[frame_index], self.flip_h, self.flip_v)
        return None

class StaticBody2D(Node2D):
    def __init__(self) -> None:
        super().__init__()

class DynamicBody2D(Node2D):
    def __init__(self) -> None:
        super().__init__()
        self.velocity = (0, 0)

class KinematicBody2D(Node2D):
    def __init__(self) -> None:
        super().__init__()
        self.velocity = (0, 0)

    def move_and_slide(self):
        self.position = (
            self.position[0] + self.velocity[0],
            self.position[1] + self.velocity[1]
        )

    

class Camera2D(Node2D):
    def __init__(self) -> None:
        super().__init__()

        self.offset = (0, 0)
        self.current : bool = True
        self.zoom = 1.0
    
class AudioPlayer(Node):
    def __init__(self) -> None:
        super().__init__()
        self._audio_resource = None
        self._volume = 1.0

    def save_data(self) -> dict:
        data = super().save_data()
        if self._audio_resource:
            data["audio"] = self._audio_resource
        return data

    def load_data(self, data: dict):
        super().load_data(data)
        if "audio" in data:
            self.audio = data["audio"]

    def play(self):
        if self._audio_resource:
            sound = self._audio_resource.get_sound()
            if sound:
                sound.play()

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, _vol: float):
        self._volume = _vol
        if self._audio_resource:
            sound = self._audio_resource.get_sound()
            if sound:
                sound.set_volume(_vol)

    @property
    def audio(self):
        return self._audio_resource

    @audio.setter
    def audio(self, value):
        from .Resources import AudioStream
        from .ResourceServer import ResourceLoader

        if isinstance(value, AudioStream):
            self._audio_resource = value
        elif isinstance(value, str):
            try:
                res = ResourceLoader.load(value)
                if isinstance(res, AudioStream):
                    self._audio_resource = res
                else:
                    self._audio_resource = AudioStream(resource_path=value)
            except Exception:
                self._audio_resource = None
        else:
            self._audio_resource = None

        if self._audio_resource:
            sound = self._audio_resource.get_sound()
            if sound:
                sound.set_volume(self._volume)

    def on_exit(self):
        try:
            if self._audio_resource:
                sound = self._audio_resource.get_sound()
                if sound:
                    sound.stop()
        except Exception:
            pass
        
        super().on_exit()

    
class TileMap2D(Node2D):
    def __init__(self) -> None:
        super().__init__()
        self._tileset_resource: Resources.Tileset2D | None = None
        self._bounds: tuple[tuple[int, int], tuple[int, int]] = ((0, 0), (1, 1))
        self._tile_data: list[list[int]] = [[-1]]

    @staticmethod
    def _normalize_bounds(bounds) -> tuple[tuple[int, int], tuple[int, int]]:
        if isinstance(bounds, (list, tuple)) and len(bounds) >= 2:
            min_raw, max_raw = bounds[0], bounds[1]
            if isinstance(min_raw, (list, tuple)) and isinstance(max_raw, (list, tuple)):
                min_x = int(min_raw[0])
                min_y = int(min_raw[1])
                max_x = int(max_raw[0])
                max_y = int(max_raw[1])
                return (
                    (min(min_x, max_x), min(min_y, max_y)),
                    (max(min_x, max_x), max(min_y, max_y)),
                )
        return ((0, 0), (0, 0))

    @staticmethod
    def _grid_dimensions(bounds) -> tuple[int, int]:
        (min_x, min_y), (max_x, max_y) = TileMap2D._normalize_bounds(bounds)
        return (max_x - min_x + 1, max_y - min_y + 1)

    def _empty_grid(self, bounds=None, fill_value: int = -1):
        target_bounds = self._bounds if bounds is None else self._normalize_bounds(bounds)
        width, height = self._grid_dimensions(target_bounds)
        return [[int(fill_value) for _ in range(width)] for _ in range(height)]

    def _normalize_tile_data(self, value, bounds=None, fill_value: int = -1):
        target_bounds = self._bounds if bounds is None else self._normalize_bounds(bounds)
        width, height = self._grid_dimensions(target_bounds)
        normalized = self._empty_grid(target_bounds, fill_value=fill_value)

        if not isinstance(value, (list, tuple)):
            return normalized

        for row_index in range(min(height, len(value))):
            row = value[row_index]
            if not isinstance(row, (list, tuple)):
                continue
            for column_index in range(min(width, len(row))):
                try:
                    normalized[row_index][column_index] = int(row[column_index])
                except Exception:
                    normalized[row_index][column_index] = int(fill_value)

        return normalized

    @property
    def tileset(self):
        return self._tileset_resource

    @property
    def bounds(self):
        return self._bounds

    @bounds.setter
    def bounds(self, value):
        self.set_bounds(value, preserve=True, fill_value=-1)

    @property
    def tile_data(self):
        return self._tile_data

    @tile_data.setter
    def tile_data(self, value):
        self._tile_data = self._normalize_tile_data(value, bounds=self._bounds)

    @tileset.setter
    def tileset(self, value):
        if isinstance(value, Resources.Tileset2D):
            self._tileset_resource = value
        elif isinstance(value, str):
            from .ResourceServer import ResourceLoader

            try:
                res = ResourceLoader.load(value)
                if isinstance(res, Resources.Tileset2D):
                    self._tileset_resource = res
                else:
                    self._tileset_resource = Resources.Tileset2D.from_path(value)
            except Exception:
                self._tileset_resource = None
        else:
            self._tileset_resource = None

    def set_bounds(self, bounds, preserve: bool = True, fill_value: int = -1):
        normalized_bounds = self._normalize_bounds(bounds)
        previous_bounds = self._bounds
        previous_data = self._tile_data

        self._bounds = normalized_bounds
        self._tile_data = self._empty_grid(normalized_bounds, fill_value=fill_value)

        if not preserve or not previous_data:
            return

        old_min, _ = previous_bounds
        new_min, _ = normalized_bounds
        old_width, old_height = self._grid_dimensions(previous_bounds)
        new_width, new_height = self._grid_dimensions(normalized_bounds)

        for old_y in range(old_height):
            for old_x in range(old_width):
                new_x = old_x + old_min[0] - new_min[0]
                new_y = old_y + old_min[1] - new_min[1]
                if 0 <= new_x < new_width and 0 <= new_y < new_height:
                    self._tile_data[new_y][new_x] = int(previous_data[old_y][old_x])

    def get_tile_id(self, tile_pos: tuple[int, int]) -> int:
        tile_x, tile_y = int(tile_pos[0]), int(tile_pos[1])
        (min_x, min_y), (max_x, max_y) = self._bounds
        if tile_x < min_x or tile_y < min_y or tile_x > max_x or tile_y > max_y:
            return -1
        row_index = tile_y - min_y
        column_index = tile_x - min_x
        return int(self._tile_data[row_index][column_index])

    def set_tile_id(self, tile_pos: tuple[int, int], tile_id: int):
        tile_x, tile_y = int(tile_pos[0]), int(tile_pos[1])
        (min_x, min_y), (max_x, max_y) = self._bounds

        if tile_x < min_x or tile_y < min_y or tile_x > max_x or tile_y > max_y:
            expanded_bounds = self._normalize_bounds(
                ((min(min_x, tile_x), min(min_y, tile_y)), (max(max_x, tile_x), max(max_y, tile_y)))
            )
            self.set_bounds(expanded_bounds, preserve=True, fill_value=-1)
            (min_x, min_y), _ = self._bounds

        row_index = tile_y - min_y
        column_index = tile_x - min_x
        self._tile_data[row_index][column_index] = int(tile_id)

        return True

    def save_data(self) -> dict:
        data = super().save_data()
        data["bounds"] = [list(self._bounds[0]), list(self._bounds[1])]
        data["tile_data"] = [list(row) for row in self._tile_data]
        if self._tileset_resource:
            data["tileset"] = self._tileset_resource
        return data

    def load_data(self, data: dict):
        base_data = {
            key: value
            for key, value in data.items()
            if key not in {"tileset", "bounds", "tile_data", "_tile_data"}
        }
        super().load_data(base_data)

        if "tileset" in data:
            self.tileset = data["tileset"]

        self._bounds = self._normalize_bounds(data.get("bounds", self._bounds))
        source_tile_data = data.get("tile_data", data.get("_tile_data", self._tile_data))
        self._tile_data = self._normalize_tile_data(source_tile_data, bounds=self._bounds)

    def tile_to_world(self, tile_pos: tuple[int, int]) -> tuple[int, int]:
        tw, th = self.tileset.tile_size if self.tileset and getattr(self.tileset, "tile_size", None) else (16, 16)
        return (tile_pos[0] * tw, tile_pos[1] * th)

    def world_to_tile(self, world_pos: tuple[int, int]) -> tuple[int, int]:
        tw, th = self.tileset.tile_size if self.tileset and getattr(self.tileset, "tile_size", None) else (16, 16)
        if tw <= 0 or th <= 0:
            return (0, 0)
        return (int(world_pos[0] // tw), int(world_pos[1] // th))

    @property
    def world_bounds(self) -> tuple[tuple[int, int], tuple[int, int]]:
        (min_x, min_y), (max_x, max_y) = self._bounds
        min_world = self.tile_to_world((min_x, min_y))
        max_world = self.tile_to_world((max_x + 1, max_y + 1))
        return (min_world, max_world)

class YSort2D(Node2D):
    def __init__(self) -> None:
        super().__init__()
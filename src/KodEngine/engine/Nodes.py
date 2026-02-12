from .NodeComponents import SpriteAnimation
from . import Resources
import pygame
import os


class Node:
    def __init__(self) -> None:
        self.name = self.__class__.__name__
        self._children = []
        self._parent: 'Node | None' = None
        self.script: str | None = None
        self.runtime_script: object | None = None
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

    def set_script(self, module_name: str):
        self.script = module_name
        self.runtime_script = Resources.load_script(module_name, self)

    
    def _update(self, _delta):
        pass

    def editor_update(self, delta):
        pass


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
        from .Resources import CollisionRectangleShape
        # Initialize with a unique default shape
        self._shape = CollisionRectangleShape(size=(32, 32))

    @property
    def shape(self):
        return self._shape

    @shape.setter
    def shape(self, value):
        from .ResourceServer import ResourceLoader
        from .Resources import CollisionShape
        
        if isinstance(value, CollisionShape):
            self._shape = value
        elif isinstance(value, str):
            # Try to load as resource
            try:
                res = ResourceLoader.load(value)
                if isinstance(res, CollisionShape):
                    self._shape = res
            except Exception:
                pass
        # If it's none or invalid, we keep previous or set default? 
        # For now let's allow setting it if valid.


class Sprite2D(Node2D):
    def __init__(self) -> None:
        super().__init__()

        self.flip_h, self.flip_v = False, False
        self._texture_resource = None
        self.position = (0,0)
        self.offset = (0,0)
    
    @property
    def texture(self):
        return self._texture_resource

    @texture.setter
    def texture(self, value):
        from .Resources import TextureResource

        if isinstance(value, TextureResource):
            self._texture_resource = value
        elif isinstance(value, str):
             from .ResourceServer import ResourceLoader
             try:
                 res = ResourceLoader.load(value)
                 if isinstance(res, TextureResource):
                     self._texture_resource = res
                 else:
                     self._texture_resource = TextureResource(resource_path=value)
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


class AnimatedSprite2D(Sprite2D):
    def __init__(self):
        super().__init__()
        self.animations: list[SpriteAnimation] = []
        self.name = "AnimatedSprite2D"
        
        self.current_animation: SpriteAnimation | None = None

    def add_animation(self, animation: SpriteAnimation):
        self.animations.append(animation)

    def play(self, name: str):
        if self.current_animation and name == self.current_animation.name:
            return

        for anim in self.animations:
            if anim.name == name:
                self.current_animation = anim
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
            return pygame.transform.flip(self.current_animation.frames_surfaces[self.current_animation.current_frame], self.flip_h, self.flip_v)
        return None

class TileMap2D(Node2D):
    def __init__(self) -> None:
        super().__init__()




class StaticBody2D(Node2D):
    def __init__(self) -> None:
        super().__init__()
        self.collision_shape : CollisionShape2D | None = None

class DynamicBody2D(Node2D):
    def __init__(self) -> None:
        super().__init__()
        self.velocity = (0, 0)
        self.collision_shape : CollisionShape2D | None = None

class KinematicBody2D(Node2D):
    def __init__(self) -> None:
        super().__init__()
        self.velocity = (0, 0)
        self.collision_shape : CollisionShape2D | None = None

class Camera2D(Node2D):
    def __init__(self) -> None:
        super().__init__()

        self.offset = (0, 0)
        self.current : bool = True
    
class AudioPlayer(Node):
    def __init__(self) -> None:
        super().__init__()
        self._audio_resource = None
        self._volume = 1.0

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
        from .Resources import AudioResource
        from .ResourceServer import ResourceLoader

        if isinstance(value, AudioResource):
            self._audio_resource = value
        elif isinstance(value, str):
            try:
                res = ResourceLoader.load(value)
                if isinstance(res, AudioResource):
                    self._audio_resource = res
                else:
                    self._audio_resource = AudioResource(file_path=value)
            except Exception:
                self._audio_resource = None
        else:
            self._audio_resource = None

        if self._audio_resource:
            sound = self._audio_resource.get_sound()
            if sound:
                sound.set_volume(self._volume)

    def _on_enter(self):
        for child in getattr(self, "_children", []):
            try:
                child._on_enter()
            except Exception:
                pass

    def on_exit(self):
        try:
            if self._audio_resource:
                sound = self._audio_resource.get_sound()
                if sound:
                    sound.stop()
        except Exception:
            pass

    

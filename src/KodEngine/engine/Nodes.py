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

    def set_script(self, module_name: str):
        self.script = module_name

    @property
    def script(self):
        return self._script_resource

    @script.setter
    def script(self, value):
        if isinstance(value, Resources.ScriptResource):
            self._script_resource = value
        elif isinstance(value, str):
            self._script_resource = Resources.ScriptResource(script_path=value)
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
        self.shape = Resources.CollisionRectangleShape(size=(32, 32))
   


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
        self.animations: list[Resources.SpriteAnimationResource] = []
        self.name = "AnimatedSprite2D"
        
        self.current_animation: Resources.SpriteAnimationResource | None = None

    def add_animation(self, animation: Resources.SpriteAnimationResource):
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
            frames = getattr(self.current_animation, "frames_surfaces", None)
            frame_index = getattr(self.current_animation, "current_frame", 0)
            if not frames:
                return None
            if frame_index < 0 or frame_index >= len(frames):
                return None
            return pygame.transform.flip(frames[frame_index], self.flip_h, self.flip_v)
        return None

class TileMap2D(Node2D):
    def __init__(self) -> None:
        super().__init__()




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

    

from KodEngine.engine.NodeComponents import SpriteAnimation

import pygame
import os

class Node:
    def __init__(self) -> None:
        self.name = self.__class__.__name__
        self._children = []
        self._parent: 'Node | None' = None
        self.script : object | None = None
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
        self.rect = ((0,0), (16,16))

class Sprite2D(Node2D):
    def __init__(self) -> None:
        super().__init__()

        self.flip_h, self.flip_v = False, False
        self._image :  pygame.Surface | None = None
        self.texture_path: str | None = None
        self.position = (0,0)
        self.offset = (0,0)


    @property
    def texture(self):
        if self._image is None:
            return None
        return pygame.transform.flip(self._image, self.flip_h, self.flip_v)
    
    @texture.setter
    def texture(self, _texture) -> None:
        if isinstance(_texture, str):
            try:
                self.texture_path = os.path.abspath(str(_texture))
            except Exception:
                self.texture_path = _texture

            try:
                self._image = pygame.image.load(str(_texture)).convert_alpha()
            except Exception:
                self._image = None
        else:
            self._image = _texture

    def _on_enter(self):
        if self._image is None and getattr(self, "texture_path", None):
            try:
                self.texture = self.texture_path
            except Exception:
                pass


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
    def texture(self):
        if self.current_animation:
            return pygame.transform.flip(self.current_animation.frames_surfaces[self.current_animation.current_frame], self.flip_h, self.flip_v)
        return None

class TileMap2D(Node2D):
    def __init__(self) -> None:
        super().__init__()

class CharacterBody2D(Node2D):
    def __init__(self) -> None:
        super().__init__()

class Camera2D(Node2D):
    def __init__(self) -> None:
        super().__init__()

        self.offset = (0, 0)
        self.current : bool = True
    
class AudioPlayer(Node):
    def __init__(self) -> None:
        super().__init__()
        self._audio = None
        self._volume = 1.0
        self.audio_path: str | None = None

    def play(self):
        if self._audio:
            self._audio.play()

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, _vol: float):
        self._volume = _vol
        if self._audio:
            self._audio.set_volume(_vol)

    @property
    def audio(self):
        return self._audio

    @audio.setter
    def audio(self, _audio_file):
        try:
            self.audio_path = os.path.abspath(_audio_file)

        except Exception:
            self.audio_path = None

        try:
            self._audio = pygame.mixer.Sound(_audio_file)
            self._audio.set_volume(self._volume)

        except Exception:
            self._audio = None

    def _on_enter(self):
        if self._audio is None and getattr(self, "audio_path", None):
            try:
                self.audio = self.audio_path
            except Exception:
                pass

        for child in getattr(self, "_children", []):
            try:
                child._on_enter()
            except Exception:
                pass

    def on_exit(self):
        try:
            if self._audio:
                try:
                    self._audio.stop()
                except Exception:
                    pass
        except Exception:
            pass

        for child in getattr(self, "_children", []):
            try:
                child.on_exit()
            except Exception:
                pass

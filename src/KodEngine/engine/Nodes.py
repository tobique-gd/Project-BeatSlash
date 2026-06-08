from abc import ABC, abstractmethod

from pygame.transform import scale

from . import Resources
import pygame
import os
import math
from . import ResourceServer
from .ErrorHandler import ErrorHandler
from enum import Enum
from . import Globals

class Node:
    """Base node for the engine scene tree."""

    def __init__(self) -> None:
        """Create a node with default tree, signal, and script state."""
        self.name = self.__class__.__name__
        self._children = []
        self._parent: 'Node | None' = None
        self._script_resource = None
        self.runtime_script: object | None = None
        self.script = None
        self._queued_for_deletion = False
        self.is_linked_scene = False
        self.linked_scene_path = None
        self._signal_connections: dict[str, list[dict]] = {}
        self._next_signal_connection_id = 1

    def connect(self, signal, callback=None, target=None, method=None, oneshot=False, allow_duplicate=False):
        """Connect a signal to a callback or method.

        Parameters
        ----------
        signal:
            Signal name to connect.
        callback:
            Callable or method name to invoke.
        target:
            Optional explicit target object for method callbacks.
        method:
            Optional method name override.
        oneshot:
            When ``True``, remove the connection after the first emit.
        allow_duplicate:
            When ``True``, permit duplicate connections.

        Returns
        -------
        int | None
            Connection id when successful, otherwise ``None``.
        """
        callback_fn = None
        method_name = None

        if isinstance(callback, str):
            method_name = callback
        elif callable(callback):
            callback_fn = callback
        elif callback is not None:
            ErrorHandler.throw_warning(
                f"Invalid callback for signal '{signal}' on node '{self.name}': expected callable or method name"
            )
            return None

        if method is not None:
            if isinstance(method, str):
                method_name = method
            else:
                ErrorHandler.throw_warning(
                    f"Invalid method for signal '{signal}' on node '{self.name}': expected string"
                )
                return None

        if callback_fn is None and method_name is None:
            ErrorHandler.throw_warning(
                f"connect() called without callable or method for signal '{signal}' on node '{self.name}'"
            )
            return None

        if signal not in self._signal_connections:
            self._signal_connections[signal] = []

        if not allow_duplicate:
            for connection in self._signal_connections[signal]:
                if (
                    connection.get("callback") is callback_fn
                    and connection.get("method") == method_name
                    and connection.get("target") is target
                ):
                    return connection.get("id")

        connection_id = self._next_signal_connection_id
        self._next_signal_connection_id += 1

        self._signal_connections[signal].append(
            {
                "id": connection_id,
                "callback": callback_fn,
                "method": method_name,
                "target": target,
                "oneshot": bool(oneshot),
            }
        )
        return connection_id

    def disconnect(self, connection_id: int):
        """Remove a signal connection by id.

        Returns
        -------
        bool
            ``True`` when the connection was removed.
        """
        for signal_name, connections in list(self._signal_connections.items()):
            for idx, connection in enumerate(connections):
                if connection.get("id") == connection_id:
                    del connections[idx]
                    if not connections:
                        self._signal_connections.pop(signal_name, None)
                    return True
        return False

    def disconnect_signal(self, signal, callback=None, target=None, method=None):
        """Remove all matching connections for a signal.

        Returns
        -------
        int
            Number of removed connections.
        """
        if signal not in self._signal_connections:
            return 0

        removed = 0
        remaining = []
        for connection in self._signal_connections[signal]:
            if self._signal_connection_matches(connection, callback=callback, target=target, method=method):
                removed += 1
            else:
                remaining.append(connection)

        if remaining:
            self._signal_connections[signal] = remaining
        else:
            self._signal_connections.pop(signal, None)
        return removed

    def get_signal_connections(self, signal=None):
        """Return signal connection metadata.

        Parameters
        ----------
        signal:
            Optional signal name to filter by.

        Returns
        -------
        list | dict
            Connections for one signal or all connections grouped by signal.
        """
        if signal is not None:
            return list(self._signal_connections.get(signal, []))
        return {name: list(connections) for name, connections in self._signal_connections.items()}

    def _signal_connection_matches(self, connection, callback=None, target=None, method=None):
        """Return whether a stored connection matches the provided filter."""
        expected_method = method
        expected_callback = callback

        if isinstance(callback, str):
            expected_method = callback
            expected_callback = None

        callback_matches = expected_callback is None or connection.get("callback") is expected_callback
        method_matches = expected_method is None or connection.get("method") == expected_method
        target_matches = target is None or connection.get("target") is target
        return callback_matches and method_matches and target_matches

    def _invoke_signal_target_method(self, target, method_name: str, *args, **kwargs):
        """Invoke a named method on a signal target when possible."""
        script_proxy_call = getattr(target, "_call", None)
        script_proxy_module = getattr(target, "_module", None)
        if callable(script_proxy_call) and script_proxy_module is not None and hasattr(script_proxy_module, method_name):
            if kwargs:
                ErrorHandler.throw_warning(
                    f"Signal method '{method_name}' on script proxy ignores keyword arguments"
                )
            script_proxy_call(method_name, *args)
            return True

        bound_method = getattr(target, method_name, None)
        if callable(bound_method):
            bound_method(*args, **kwargs)
            return True

        return False

    def change_scene_to(self, scene_path):
        """Load a scene and make it the active scene.

        Parameters
        ----------
        scene_path:
            Path to the scene file.

        Returns
        -------
        bool
            ``True`` when the scene switch succeeds.
        """
        if not scene_path:
            ErrorHandler.throw_warning(f"change_scene_to() called on node '{self.name}' without a scene path")
            return False

        app = getattr(Globals, "APP", None)
        if app is None:
            ErrorHandler.throw_warning(f"change_scene_to() called on node '{self.name}' but no active app is available")
            return False

        resolved_scene_path = ResourceServer.ResourceLoader.resolve_path(scene_path)
        scene = ResourceServer.SceneLoader.load(resolved_scene_path)
        if scene is None:
            ErrorHandler.throw_warning(f"Failed to change scene on node '{self.name}': could not load '{scene_path}'")
            return False

        app.set_scene(scene)
        return True

    def quit(self):
        """Request application shutdown.

        Returns
        -------
        bool
            ``True`` when an active app was found and marked for exit.
        """
        app = getattr(Globals, "APP", None)
        if app is None:
            ErrorHandler.throw_warning(f"quit() called on node '{self.name}' but no active app is available")
            return False

        app.kill()
        return True

    def _invoke_signal_connection(self, connection, *args, **kwargs):
        """Invoke one stored signal connection.

        Returns
        -------
        bool
            ``True`` when a callable or target method was executed.
        """
        callback = connection.get("callback")
        if callable(callback):
            callback(*args, **kwargs)
            return True

        method_name = connection.get("method")
        if not method_name:
            return False

        explicit_target = connection.get("target")
        if explicit_target is not None:
            return self._invoke_signal_target_method(explicit_target, method_name, *args, **kwargs)

        current_node = self
        while current_node is not None:
            runtime_script = getattr(current_node, "runtime_script", None)
            if runtime_script is not None and self._invoke_signal_target_method(runtime_script, method_name, *args, **kwargs):
                return True

            if self._invoke_signal_target_method(current_node, method_name, *args, **kwargs):
                return True

            parent = getattr(current_node, "_parent", None)
            current_node = parent if isinstance(parent, Node) else None

        return False
    
    def preload(self, scene_path: str):
        """Load a scene without making it the active scene."""
        resolved_scene_path = ResourceServer.ResourceLoader.resolve_path(scene_path)
        scene = ResourceServer.SceneLoader.load(resolved_scene_path)
        if scene is None:
            ErrorHandler.throw_warning(f"Failed to preload scene on node '{self.name}': could not load '{scene_path}'")
            return None
        return scene
    
    def instantiate(self, scene):
        """Return the root node of a loaded scene."""
        root = scene.root if scene else None
        if root is not None:
            root._on_enter()

        return root.clone() if root else None
        

    def emit_signal(self, signal, *args, **kwargs):
        """Emit a signal and invoke all matching connections.

        Returns
        -------
        int
            Number of callbacks that were successfully called.
        """

        callbacks = list(self._signal_connections.get(signal, []))
        oneshot_to_remove = []
        called_count = 0

        for callback in callbacks:
            try:
                called = self._invoke_signal_connection(callback, *args, **kwargs)
                if called:
                    called_count += 1
                else:
                    ErrorHandler.throw_warning(
                        f"No valid callback target while emitting signal '{signal}' on node '{self.name}'"
                    )

                if callback.get("oneshot"):
                    oneshot_to_remove.append(callback.get("id"))
            except Exception as e:
                ErrorHandler.throw_error(f"Error in signal callback for signal '{signal}' on node '{self.name}': {e}")

        for connection_id in oneshot_to_remove:
            if connection_id is not None:
                self.disconnect(connection_id)

        return called_count

    def _on_enter(self):
        """Propagate enter notifications to child nodes."""
        for child in getattr(self, "_children", []):
            try:
                child._on_enter()
            except Exception:
                pass

    def on_exit(self):
        """Propagate exit notifications to child nodes."""
        for child in getattr(self, "_children", []):
            try:
                child.on_exit()
            except Exception:
                pass

    def add_child(self, _node):
        """Attach a child node to this node."""
        self._children.append(_node)
        _node._parent = self
        _node._on_enter()

        runtime_script = getattr(_node, "runtime_script", None)
        if runtime_script is not None and hasattr(runtime_script, "_ready"):
            try:
                runtime_script._ready()
                
                
            except Exception:
                pass

    def remove_child(self, _node):
        """Detach a child node from this node."""
        if _node in self._children:
            _node._parent = None
            self._children.remove(_node)
    
    def queue_free(self):
        """Mark the node for deferred deletion."""
        self._queued_for_deletion = True
    
    def clone(self):
        """Create a serialized copy of the node tree."""
        data = ResourceServer.SceneLoader.serialize_node(self)
        data_copy = data.copy()
        des = ResourceServer.SceneLoader.deserialize_node(data_copy)
        return des

    def get_node(self, _path_to_child: str):
        """Resolve a descendant by slash-separated path."""
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
        """Return the child at ``index`` or ``None`` when out of range."""
        if index < 0 or index >= len(self._children):
            return None
        return self._children[index]

    def get_nodes_by_type(self, node_type):
        """Return all direct children that match ``node_type``."""
        found_nodes = []
        for child in self._children:
            if isinstance(child, node_type):
                found_nodes.append(child)

        return found_nodes

    def set_script(self, module_name: str):
        """Assign a script resource or script path to the node."""
        self.script = module_name

    def reparent_to(self, new_parent: 'Node'):
        """Move the node under a new parent."""
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
        """Per-frame update hook for subclasses."""
        pass

    def editor_update(self, delta):
        """Editor-only update hook for subclasses."""
        pass

    def _input(self, _event):
        """Input hook for subclasses."""
        pass

    def save_data(self) -> dict:
        """Serialize node state into a dictionary."""
        data = {}

        for name, value in vars(self).items():
            if name.startswith("_"):
                continue
            if name in ("script", "runtime_script"):
                continue
            if callable(value):
                continue

            data[name] = value

        if self._script_resource:
            data["script"] = self._script_resource

        return data

    def load_data(self, data: dict):
        """Load node state from serialized data."""
        for name, value in data.items():
            if hasattr(self, name):
                try:
                    setattr(self, name, value)
                except Exception as e:
                    print(f"Error setting {name} on {self.name}: {e}")

            children_data = data.get("_children", [])
            for child_data in children_data:
                child = Node()
                self.add_child(child)
                child.load_data(child_data)


class Node2D(Node):
    """Base node type with 2D transform state."""

    def __init__(self) -> None:
        """Create a 2D node with default transform values."""
        super().__init__()
        self.position: tuple[float, float] = (0, 0)
        self.rotation: float = 0.0
        self.scale: tuple[float, float] = (1, 1)
        self.z_index = 0
        self.visible = True

    @staticmethod
    def _coerce_rotation_value(value) -> float:
        """Convert a rotation-like value to a float in degrees."""
        if isinstance(value, (list, tuple)):
            if not value:
                return 0.0
            value = value[0]

        try:
            return float(value)
        except Exception:
            return 0.0

    def load_data(self, data: dict):
        """Load transform state from serialized data."""
        super().load_data(data)
        self.rotation = self._coerce_rotation_value(self.rotation)

    @staticmethod
    def _rotate_point(point: tuple[float, float], angle_degrees: float) -> tuple[float, float]:
        """Rotate a 2D point around the origin by ``angle_degrees``."""
        radians = math.radians(float(angle_degrees))
        cos_angle = math.cos(radians)
        sin_angle = math.sin(radians)
        x, y = float(point[0]), float(point[1])
        return (
            (x * cos_angle) - (y * sin_angle),
            (x * sin_angle) + (y * cos_angle),
        )

    @staticmethod
    def _safe_divide(point: tuple[float, float], scale: tuple[float, float]) -> tuple[float, float]:
        """Divide a point by scale values while avoiding division by zero."""
        scale_x = float(scale[0]) if len(scale) > 0 else 1.0
        scale_y = float(scale[1]) if len(scale) > 1 else 1.0
        return (
            point[0] / scale_x if scale_x not in (0.0, -0.0) else point[0],
            point[1] / scale_y if scale_y not in (0.0, -0.0) else point[1],
        )



    @property
    def global_position(self):
        if self._parent is None:
            return self.position
        if isinstance(self._parent, Node2D):
            parent_position = self._parent.global_position
            parent_rotation = self._coerce_rotation_value(self._parent.global_rotation)
            parent_scale = getattr(self._parent, "global_scale", (1, 1))
            scaled_position = self._safe_divide(self.position, (1.0, 1.0))
            scaled_position = (
                scaled_position[0] * float(parent_scale[0]),
                scaled_position[1] * float(parent_scale[1]),
            )
            rotated_position = self._rotate_point(scaled_position, parent_rotation)
            return (
                parent_position[0] + rotated_position[0],
                parent_position[1] + rotated_position[1],
            )
        return self.position


    @global_position.setter
    def global_position(self, value: tuple[float, float]) -> None:
        if self._parent is None:
            self.position = value
        elif isinstance(self._parent, Node2D):
            parent_global = self._parent.global_position
            parent_rotation = self._coerce_rotation_value(self._parent.global_rotation)
            parent_scale = getattr(self._parent, "global_scale", (1, 1))
            relative_position = (
                float(value[0]) - float(parent_global[0]),
                float(value[1]) - float(parent_global[1]),
            )
            unrotated_position = self._rotate_point(relative_position, -parent_rotation)
            local_position = self._safe_divide(unrotated_position, parent_scale)
            self.position = local_position
        else:
            self.position = value

    @property
    def global_scale(self):
        if self._parent is not None and hasattr(self._parent, 'global_scale'):
            parent_scale = self._parent.global_scale # type: ignore
            return (self.scale[0] * parent_scale[0], self.scale[1] * parent_scale[1])
        return self.scale

    @global_scale.setter
    def global_scale(self, value: tuple[float, float]):
        self.scale = value

    @property
    def global_rotation(self) -> float:
        rotation = self._coerce_rotation_value(self.rotation)
        if self._parent is not None and isinstance(self._parent, Node2D):
            return rotation + self._coerce_rotation_value(self._parent.global_rotation)
        return rotation

    @global_rotation.setter
    def global_rotation(self, value: float):
        if self._parent is not None and isinstance(self._parent, Node2D):
            self.rotation = self._coerce_rotation_value(value) - self._coerce_rotation_value(self._parent.global_rotation)
        else:
            self.rotation = self._coerce_rotation_value(value)

    @property
    def global_visible(self) -> bool:
        if not self.visible:
            return False
        if isinstance(self._parent, Node2D):
            return self._parent.global_visible
        return True


class CollisionObject2D(Node2D, ABC):
    """Base node for 2D collision bodies and areas."""

    def __init__(self) -> None:
        """Create a collision object with empty layers and masks."""
        super().__init__()
        
        self.collision_layers = []
        self.collision_masks = []
        

    @abstractmethod
    def _abstract_collision_object(self) -> None:
        pass

class CollisionShape2D(Node2D, ABC):
    """Base node for collision shape components."""

    def __init__(self) -> None:
        """Create a collision shape node."""
        super().__init__()

    @abstractmethod
    def _abstract_collision_shape(self) -> None:
        pass

class RectangleCollisionShape2D(CollisionShape2D):
    """Axis-aligned rectangle collision shape node."""

    def __init__(self) -> None:
        """Create a default rectangle collision shape."""
        super().__init__()
        self.size = (32, 32)

    def _abstract_collision_shape(self) -> None:
        """Placeholder implementation for the abstract collision hook."""
        pass

class Sprite2D(Node2D):
    """Renderable 2D sprite node."""

    def __init__(self) -> None:
        """Create a sprite node with default texture state."""
        super().__init__()

        self.flip_h, self.flip_v = False, False
        self.tint = (1.0, 1.0, 1.0)
        self._texture_resource = None
        self.position = (0,0)
        self.offset = (0,0)
    
    def save_data(self) -> dict:
        """Serialize sprite-specific properties."""
        data = super().save_data()
        if self._texture_resource:
            data["texture"] = self._texture_resource
        return data

    def load_data(self, data: dict):
        """Load sprite-specific properties from serialized data."""
        super().load_data(data)
        if "texture" in data:
            self.texture = data["texture"]

    @property
    def texture(self):
        return self._texture_resource

    @texture.setter
    def texture(self, value):
        """Assign a texture resource or resolve one from a file path."""
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
        """Return the rendered sprite surface or ``None``."""
        if self._texture_resource:
            surf = self._texture_resource.get_texture()
            if surf:
                return pygame.transform.flip(surf, self.flip_h, self.flip_v)
        return None


class AnimatedSprite2D(Sprite2D):
    """Sprite node that advances through a resource-backed animation."""

    def __init__(self):
        """Create an animated sprite with no active animation."""
        super().__init__()
        self.animations: list[Resources.SpriteAnimation] = []
        self.name = "AnimatedSprite2D"
        
        self._current_animation: Resources.SpriteAnimation | None = None

    @property
    def current_animation(self):
        return self._current_animation

    @current_animation.setter
    def current_animation(self, value):
        """Assign the active animation resource or resolve it from a path."""
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
        """Serialize the sprite and current animation state."""
        data = super().save_data()
        if self.current_animation:
             data["current_animation"] = {
                 "name": self.current_animation.name,
                 "current_frame": self.current_animation.current_frame,
                 "time_accumulator": self.current_animation.time_accumulator
             }
        return data

    def load_data(self, data: dict):
        """Restore animated sprite state from serialized data."""
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
        """Register an animation resource on the sprite."""
        self.animations.append(animation)

    def play(self, name: str):
        """Activate an animation by name and rewind it."""
        if self._current_animation and name == self._current_animation.name and not self._current_animation.finished:
            return

        for anim in self.animations:
            if anim.name == name:
                self._current_animation = anim
                anim.current_frame = 0
                anim.time_accumulator = 0
                anim.finished = False
                break

    def _update(self, delta: float):
        """Advance the active animation during runtime."""
        if self.current_animation:
            was_finished = self.current_animation.finished
            self.current_animation.update(delta)
            if not was_finished and self.current_animation.finished:
                self.emit_signal("animation_finished", self.current_animation.name)
    
    def editor_update(self, delta):
        """Advance the active animation while running in the editor."""
        if self.current_animation:
            was_finished = self.current_animation.finished
            self.current_animation.update(delta)
            if not was_finished and self.current_animation.finished:
                self.emit_signal("animation_finished", self.current_animation.name)

    @property
    def image(self):
        """Return the current animation frame as a surface."""
        if self.current_animation:
            frames = getattr(self.current_animation, "frames_surfaces", None)
            frame_index = getattr(self.current_animation, "current_frame", 0)
            if not frames:
                return None
            if frame_index < 0 or frame_index >= len(frames):
                return None
            return pygame.transform.flip(frames[frame_index], self.flip_h, self.flip_v)
        return None

class StaticBody2D(CollisionObject2D):
    """Non-moving collision body."""

    def __init__(self) -> None:
        """Create a static body."""
        super().__init__()

    def _abstract_collision_object(self) -> None:
        """Placeholder implementation for the abstract collision hook."""
        pass

class DynamicBody2D(CollisionObject2D):
    """Physics body that integrates velocity each frame."""

    def __init__(self) -> None:
        """Create a dynamic body with zero velocity."""
        super().__init__()
        self.velocity = (0, 0)

    def _abstract_collision_object(self) -> None:
        """Placeholder implementation for the abstract collision hook."""
        pass

class KinematicBody2D(CollisionObject2D):
    """Collision body that moves explicitly via script or solver."""

    def __init__(self) -> None:
        """Create a kinematic body with zero velocity."""
        super().__init__()
        self.velocity = (0, 0)

    def _abstract_collision_object(self) -> None:
        """Placeholder implementation for the abstract collision hook."""
        pass

    def move_and_slide(self):
        """Apply the stored velocity directly to the global position."""
        self.global_position = (
            self.global_position[0] + self.velocity[0],
            self.global_position[1] + self.velocity[1]
        )

    

class Camera2D(Node2D):
    """2D camera node used by the renderer."""

    def __init__(self) -> None:
        """Create a camera with default offset, zoom, and limits."""
        super().__init__()

        self.offset = (0, 0)
        self.current : bool = True
        self.zoom = 1.0
        self.limit_min : tuple[float, float] = (float(-1), float(-1))
        self.limit_max : tuple[float, float] = (float(-1), float(-1))

class AudioPlayer(Node):
    """Node that plays an audio resource through pygame mixer."""

    def __init__(self):
        super().__init__()
        self._audio_resource = None
        self._volume = 1.0
        self._channel = None  # track the specific channel

    def play(self):
        if self._audio_resource:
            sound = self._audio_resource.get_sound()
            if sound:
                self._channel = sound.play()

    def _process(self, delta):
        if self._channel is not None:
            if not self._channel.get_busy():
                self._channel = None
                self.on_finished()

    def save_data(self) -> dict:
        """Serialize the audio player state."""
        data = super().save_data()
        if self._audio_resource:
            data["audio"] = self._audio_resource
        return data

    def load_data(self, data: dict):
        """Restore the audio player state from serialized data."""
        super().load_data(data)
        if "audio" in data:
            self.audio = data["audio"]

    
    def on_finished(self):
        """Emit a signal when audio playback finishes."""
        self.emit_signal("finished")

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, _vol: float):
        """Set playback volume for the assigned audio resource."""
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
        """Assign an audio resource or resolve one from a file path."""
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
        """Stop audio playback before the node leaves the scene tree."""
        try:
            if self._audio_resource:
                sound = self._audio_resource.get_sound()
                if sound:
                    sound.stop()
        except Exception:
            pass
        
        super().on_exit()

    
class TileMap2D(Node2D):
    """Node that stores and renders layered tile data."""

    def __init__(self) -> None:
        """Create an empty tilemap with a default 0-layer grid."""
        super().__init__()
        self._tileset_resource: Resources.Tileset2D | None = None
        self._bounds: tuple[tuple[int, int], tuple[int, int]] = ((0, 0), (1, 1))
        self._tile_layers: dict[int, list[list[int]]] = {0: self._empty_grid(self._bounds, fill_value=-1)}
        self._tile_data: list[list[int]] = self._tile_layers[0]
        self._chunked_tile_data: dict[int, dict[tuple[int, int], list[tuple[int, int, int]]]] = {}
        self._chunk_size = 8
        
    
    def _on_enter(self):
        """Rebuild chunk data when the tilemap enters the scene tree."""
        self.preprocess_tile_data()

    @property
    def chunk_size(self):
        return self._chunk_size
    
    @chunk_size.setter
    def chunk_size(self, value):
        try:
            new_size = int(value)
            if new_size > 0:
                self._chunk_size = new_size
                self.preprocess_tile_data()
        except Exception:
            pass

    def preprocess_tile_data(self):
        """Convert layer grids into chunked tile data for rendering."""
        self._chunked_tile_data = {}
        (min_x, min_y), _ = self._bounds
        
        chunk_area = self.chunk_size * self.chunk_size

        for layer_index, layer_data in self._tile_layers.items():
            chunked_layer = {}
            for y, row in enumerate(layer_data):
                for x, tile_id in enumerate(row):
                    if tile_id == -1:
                        continue
                    
                    abs_tx = x + min_x
                    abs_ty = y + min_y
                    
                    cx, cy = abs_tx // self.chunk_size, abs_ty // self.chunk_size
            
                    rx, ry = abs_tx % self.chunk_size, abs_ty % self.chunk_size
                    
                    if (cx, cy) not in chunked_layer:
                        chunked_layer[(cx, cy)] = [-1] * chunk_area
                    
                    chunked_layer[(cx, cy)][ry * self.chunk_size + rx] = tile_id
            
            self._chunked_tile_data[layer_index] = chunked_layer

    def shrink_to_fit(self, fill_value: int = -1):
        """Trim tile bounds to the smallest rectangle that contains tiles."""
        min_x, min_y = None, None
        max_x, max_y = None, None
        for layer in self._tile_layers.values():
            for y, row in enumerate(layer):
                for x, val in enumerate(row):
                    if val != fill_value:
                        abs_x = x + self._bounds[0][0]
                        abs_y = y + self._bounds[0][1]
                        if min_x is None or abs_x < min_x:
                            min_x = abs_x
                        if min_y is None or abs_y < min_y:
                            min_y = abs_y
                        if max_x is None or abs_x > max_x:
                            max_x = abs_x
                        if max_y is None or abs_y > max_y:
                            max_y = abs_y
        if min_x is not None and min_y is not None and max_x is not None and max_y is not None:
            self.set_bounds(((min_x, min_y), (max_x, max_y)), preserve=True, fill_value=fill_value)
        else:
            self.set_bounds(((0, 0), (0, 0)), preserve=False, fill_value=fill_value)

    @staticmethod
    def _normalize_bounds(bounds) -> tuple[tuple[int, int], tuple[int, int]]:
        """Normalize a bounds payload into ordered integer corners."""
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
        """Return the width and height implied by a bounds tuple."""
        (min_x, min_y), (max_x, max_y) = TileMap2D._normalize_bounds(bounds)
        return (max_x - min_x + 1, max_y - min_y + 1)

    def _empty_grid(self, bounds=None, fill_value: int = -1):
        """Create a grid filled with the provided value."""
        target_bounds = self._bounds if bounds is None else self._normalize_bounds(bounds)
        width, height = self._grid_dimensions(target_bounds)
        return [[int(fill_value) for _ in range(width)] for _ in range(height)]

    def _normalize_tile_data(self, value, bounds=None, fill_value: int = -1):
        """Normalize arbitrary tile data into a rectangular integer grid."""
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

    @staticmethod
    def _normalize_layer_index(layer) -> int:
        """Coerce a layer key into an integer index."""
        try:
            return int(layer)
        except Exception:
            return 0

    def _normalize_tile_layers(self, value, bounds=None, fill_value: int = -1):
        """Normalize one or more tile layers into internal storage format."""
        target_bounds = self._bounds if bounds is None else self._normalize_bounds(bounds)
        normalized_layers: dict[int, list[list[int]]] = {}

        if isinstance(value, dict):
            for layer_key, layer_data in value.items():
                layer_index = self._normalize_layer_index(layer_key)
                normalized_layers[layer_index] = self._normalize_tile_data(
                    layer_data,
                    bounds=target_bounds,
                    fill_value=fill_value,
                )
        elif isinstance(value, (list, tuple)):
            normalized_layers[0] = self._normalize_tile_data(value, bounds=target_bounds, fill_value=fill_value)

        if 0 not in normalized_layers:
            normalized_layers[0] = self._empty_grid(target_bounds, fill_value=fill_value)

        return {layer: normalized_layers[layer] for layer in sorted(normalized_layers.keys())}

    @property
    def tileset(self):
        """Return the active tileset resource."""
        return self._tileset_resource

    @property
    def bounds(self):
        """Return the tilemap bounds in tile coordinates."""
        return self._bounds

    @bounds.setter
    def bounds(self, value):
        self.set_bounds(value, preserve=True, fill_value=-1)

    @property
    def tile_layers(self):
        """Return the internal tile layer mapping."""
        return self._tile_layers

    @tile_layers.setter
    def tile_layers(self, value):
        self._tile_layers = self._normalize_tile_layers(value, bounds=self._bounds)
        self.shrink_to_fit()

    @tileset.setter
    def tileset(self, value):
        """Assign a tileset resource or resolve one from a file path."""
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
        """Resize the tilemap bounds, optionally preserving existing tiles."""
        normalized_bounds = self._normalize_bounds(bounds)
        previous_bounds = self._bounds
        previous_layers = self._normalize_tile_layers(self._tile_layers, bounds=previous_bounds, fill_value=fill_value)

        self._bounds = normalized_bounds
        empty_layer = self._empty_grid(normalized_bounds, fill_value=fill_value)
        self._tile_layers = {0: empty_layer}

        if not preserve or not previous_layers:
            return

        old_min, _ = previous_bounds
        new_min, _ = normalized_bounds
        old_width, old_height = self._grid_dimensions(previous_bounds)
        new_width, new_height = self._grid_dimensions(normalized_bounds)

        remapped_layers: dict[int, list[list[int]]] = {}
        for layer_index, previous_data in previous_layers.items():
            new_layer_data = self._empty_grid(normalized_bounds, fill_value=fill_value)
            for old_y in range(old_height):
                for old_x in range(old_width):
                    new_x = old_x + old_min[0] - new_min[0]
                    new_y = old_y + old_min[1] - new_min[1]
                    if 0 <= new_x < new_width and 0 <= new_y < new_height:
                        new_layer_data[new_y][new_x] = int(previous_data[old_y][old_x])
            remapped_layers[int(layer_index)] = new_layer_data

        if 0 not in remapped_layers:
            remapped_layers[0] = self._empty_grid(normalized_bounds, fill_value=fill_value)
        self._tile_layers = {layer: remapped_layers[layer] for layer in sorted(remapped_layers.keys())}

    def ensure_layer(self, layer: int, fill_value: int = -1):
        """Ensure a layer grid exists and return it."""
        layer_index = self._normalize_layer_index(layer)
        if layer_index not in self._tile_layers:
            self._tile_layers[layer_index] = self._empty_grid(self._bounds, fill_value=fill_value)
            self._tile_layers = {layer_id: self._tile_layers[layer_id] for layer_id in sorted(self._tile_layers.keys())}
        return self._tile_layers[layer_index]

    def get_tile_id(self, tile_pos: tuple[int, int], layer: int = 0) -> int:
        """Return the tile id at a coordinate for the requested layer."""
        tile_x, tile_y = int(tile_pos[0]), int(tile_pos[1])
        (min_x, min_y), (max_x, max_y) = self._bounds
        if tile_x < min_x or tile_y < min_y or tile_x > max_x or tile_y > max_y:
            return -1
        layer_index = self._normalize_layer_index(layer)
        layer_data = self._tile_layers.get(layer_index)
        if not isinstance(layer_data, list):
            return -1
        row_index = tile_y - min_y
        column_index = tile_x - min_x
        return int(layer_data[row_index][column_index])

    def set_tile_id(self, tile_pos: tuple[int, int], tile_id: int, layer: int = 0):
        """Set a tile id and grow the tilemap bounds when needed.

        Returns
        -------
        bool
            Always returns ``True`` after the tile is written.
        """
        tile_x, tile_y = int(tile_pos[0]), int(tile_pos[1])
        (min_x, min_y), (max_x, max_y) = self._bounds
        layer_index = self._normalize_layer_index(layer)

        if tile_x < min_x or tile_y < min_y or tile_x > max_x or tile_y > max_y:
            expanded_bounds = self._normalize_bounds(
                ((min(min_x, tile_x), min(min_y, tile_y)), (max(max_x, tile_x), max(max_y, tile_y)))
            )
            self.set_bounds(expanded_bounds, preserve=True, fill_value=-1)
            (min_x, min_y), _ = self._bounds

        layer_data = self.ensure_layer(layer_index, fill_value=-1)
        row_index = tile_y - min_y
        column_index = tile_x - min_x
        layer_data[row_index][column_index] = int(tile_id)
        self.shrink_to_fit(fill_value=-1)
        self.preprocess_tile_data()
        return True

    def get_layer_indices(self) -> list[int]:
        """Return the sorted list of layer indices in the tilemap."""
        return sorted(int(layer) for layer in self._tile_layers.keys())

    def save_data(self) -> dict:
        """Serialize the tilemap state."""
        data = super().save_data()
        data["bounds"] = [list(self._bounds[0]), list(self._bounds[1])]
        data["tile_layers"] = {
            str(layer): [list(row) for row in layer_data]
            for layer, layer_data in sorted(self._tile_layers.items(), key=lambda item: int(item[0]))
        }
        if self._tileset_resource:
            data["tileset"] = self._tileset_resource
        return data

    def load_data(self, data: dict):
        """Restore tilemap state from serialized data."""
        base_data = {
            key: value
            for key, value in data.items()
            if key not in {"tileset", "bounds", "tile_layers", "_tile_layers"}
        }
        super().load_data(base_data)

        if "tileset" in data:
            self.tileset = data["tileset"]

        self._bounds = self._normalize_bounds(data.get("bounds", self._bounds))
        source_tile_layers = data.get("tile_layers", data.get("_tile_layers", None))
        if source_tile_layers is not None:
            self._tile_layers = self._normalize_tile_layers(source_tile_layers, bounds=self._bounds)


    def tile_to_world(self, tile_pos: tuple[int, int]) -> tuple[int, int]:
        """Convert tile coordinates into world coordinates."""
        tw, th = self.tileset.tile_size if self.tileset and getattr(self.tileset, "tile_size", None) else (16, 16)
        return (tile_pos[0] * tw, tile_pos[1] * th)

    def world_to_tile(self, world_pos: tuple[int, int]) -> tuple[int, int]:
        """Convert world coordinates into tile coordinates."""
        tw, th = self.tileset.tile_size if self.tileset and getattr(self.tileset, "tile_size", None) else (16, 16)
        if tw <= 0 or th <= 0:
            return (0, 0)
        return (int(world_pos[0] // tw), int(world_pos[1] // th))

    @property
    def world_bounds(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """Return world-space bounds for the tilemap."""
        (min_x, min_y), (max_x, max_y) = self._bounds
        min_world = self.tile_to_world((min_x, min_y))
        max_world = self.tile_to_world((max_x + 1, max_y + 1))
        return (min_world, max_world)

class YSort2D(Node2D):
    """Marker node that causes descendants to render sorted by Y value."""

    def __init__(self) -> None:
        """Create a Y-sort node."""
        super().__init__()

class Area2D(CollisionObject2D):
    """Collision area node that tracks overlapping bodies and areas."""

    def __init__(self) -> None:
        """Create an area with body and area overlap tracking enabled."""
        super().__init__()

        self.collide_with_areas = True
        self.collide_with_bodies = True
        self._overlapping_areas = []
        self._overlapping_bodies = []

    def _abstract_collision_object(self) -> None:
        """Placeholder implementation for the abstract collision hook."""
        pass

    def get_overlapping_bodies(self) -> list[CollisionObject2D]:
        """Return bodies currently overlapping the area."""
        return self._overlapping_bodies

    def get_overlapping_areas(self) -> list['Area2D']:
        """Return areas currently overlapping the area."""
        return self._overlapping_areas
    




class Control(Node):
    """Base UI node with anchoring, layout, and font settings."""

    DEFAULT_FONT_SIZE = 14
    DEFAULT_FONT_COLOR = (245, 245, 245, 255)
    DEFAULT_PADDING = (4, 4, 4, 4)
    DEFAULT_GAP = 4
    DEFAULT_BG_COLOR = (58, 62, 72, 255)
    DEFAULT_TINT = (1.0, 1.0, 1.0, 1.0)

    class AnchorType(Enum):
        TOP_LEFT = "TOP_LEFT"
        TOP_CENTER = "TOP_CENTER"
        TOP_RIGHT = "TOP_RIGHT"
        CENTER_LEFT = "CENTER_LEFT"
        CENTER = "CENTER"
        CENTER_RIGHT = "CENTER_RIGHT"
        BOTTOM_LEFT = "BOTTOM_LEFT"
        BOTTOM_CENTER = "BOTTOM_CENTER"
        BOTTOM_RIGHT = "BOTTOM_RIGHT"
        NONE = "NONE"
        FULL_RECT = "FULL_RECT"


    def __init__(self) -> None:
        """Create a control with default layout and typography state."""
        super().__init__()
        self.anchor = self.AnchorType.NONE
        self.position: tuple[float, float] = (0, 0)
        self._anchor_offset: tuple[float, float] = (0, 0)
        self.size: tuple[float, float] = (0, 0)
        self.z_index = 0
        
        self.font : Resources.Font = Resources.Font()
        self.font_size: int = self.DEFAULT_FONT_SIZE
        self.font_color: tuple[int, int, int, int] = self.DEFAULT_FONT_COLOR
        self.padding: tuple[int, int, int, int] = self.DEFAULT_PADDING
        self.bg_color: tuple[int, int, int, int] = self.DEFAULT_BG_COLOR
        self.tint: tuple[float, float, float, float] = self.DEFAULT_TINT

    @staticmethod
    def _coerce_tint_value(value) -> tuple[float, float, float, float]:
        """Normalize a tint value to RGBA multipliers."""
        if not isinstance(value, (list, tuple)) or len(value) < 3:
            return Control.DEFAULT_TINT

        try:
            red = float(value[0])
            green = float(value[1])
            blue = float(value[2])
            alpha = float(value[3]) if len(value) > 3 else 1.0
        except (TypeError, ValueError, IndexError):
            return Control.DEFAULT_TINT

        return (
            max(0.0, min(1.0, red)),
            max(0.0, min(1.0, green)),
            max(0.0, min(1.0, blue)),
            max(0.0, min(1.0, alpha)),
        )
        

    def load_data(self, data: dict):
        """Restore control-specific state from serialized data."""
        super().load_data(data)
        if "anchor" in data and isinstance(data["anchor"], str):
            try:
                self.anchor = self.AnchorType[data["anchor"]]
            except (KeyError, ValueError):
                self.anchor = self.AnchorType.NONE

        if hasattr(self, "tint"):
            self.tint = self._coerce_tint_value(getattr(self, "tint", self.DEFAULT_TINT))

    def _layout_parent_rect(self, viewport_size=None, parent_rect=None):
        """Return the rectangle used to resolve this control's anchors."""
        if parent_rect is not None:
            return parent_rect

        if isinstance(self._parent, Control):
            return (
                float(self._parent.global_position[0]),
                float(self._parent.global_position[1]),
                float(self._parent.size[0]),
                float(self._parent.size[1]),
            )

        if viewport_size is not None:
            return (0.0, 0.0, float(viewport_size[0]), float(viewport_size[1]))

        return (float(self.global_position[0]), float(self.global_position[1]), float(self.size[0]), float(self.size[1]))

    def _resolve_anchor(self, parent_rect):
        """Compute the control's anchor offset from a parent rectangle."""
        _, _, parent_w, parent_h = parent_rect
        width = float(self.size[0])
        height = float(self.size[1])

        if self.anchor == self.AnchorType.NONE:
            self._anchor_offset = (0.0, 0.0)
            return

        if self.anchor == self.AnchorType.FULL_RECT:
            self._anchor_offset = (0.0, 0.0)
            self.size = (max(0.0, parent_w), max(0.0, parent_h))
            return

        anchor_positions = {
            self.AnchorType.TOP_LEFT: (0.0, 0.0),
            self.AnchorType.TOP_CENTER: ((parent_w - width) / 2.0, 0.0),
            self.AnchorType.TOP_RIGHT: (parent_w - width, 0.0),
            self.AnchorType.CENTER_LEFT: (0.0, (parent_h - height) / 2.0),
            self.AnchorType.CENTER: ((parent_w - width) / 2.0, (parent_h - height) / 2.0),
            self.AnchorType.CENTER_RIGHT: (parent_w - width, (parent_h - height) / 2.0),
            self.AnchorType.BOTTOM_LEFT: (0.0, parent_h - height),
            self.AnchorType.BOTTOM_CENTER: ((parent_w - width) / 2.0, parent_h - height),
            self.AnchorType.BOTTOM_RIGHT: (parent_w - width, parent_h - height),
        }

        local_position = anchor_positions.get(self.anchor)
        if local_position is not None:
            self._anchor_offset = local_position

    def _content_rect(self):
        """Return the control's content rectangle in global coordinates."""
        return (
            float(self.global_position[0]),
            float(self.global_position[1]),
            float(self.size[0]),
            float(self.size[1]),
        )

    def _layout_children(self, viewport_size=None):
        """Lay out child controls within this control's content area."""
        for child in self._children:
            if isinstance(child, Control):
                child.process_ui(viewport_size, parent_rect=self._content_rect(), apply_anchor=True)

    def process_ui(self, viewport_size=None, parent_rect=None, apply_anchor=True):
        """Resolve anchors and lay out child controls."""
        if apply_anchor:
            self._resolve_anchor(self._layout_parent_rect(viewport_size, parent_rect))

        self._layout_children(viewport_size)

    @property
    def global_position(self):
        """Return the control's global position including anchor offset."""
        if self._parent is None:
            return (self.position[0] + self._anchor_offset[0], self.position[1] + self._anchor_offset[1])
        if isinstance(self._parent, Control):
            p = self._parent.global_position
            return (
                self.position[0] + self._anchor_offset[0] + p[0],
                self.position[1] + self._anchor_offset[1] + p[1],
            )
        return (self.position[0] + self._anchor_offset[0], self.position[1] + self._anchor_offset[1])

    @global_position.setter
    def global_position(self, value: tuple[float, float]) -> None:
        """Set the control's global position while respecting anchors."""
        if self._parent is None:
            self.position = (
                value[0] - self._anchor_offset[0],
                value[1] - self._anchor_offset[1],
            )
        elif isinstance(self._parent, Control):
            parent_global = self._parent.global_position
            self.position = (
                value[0] - parent_global[0] - self._anchor_offset[0],
                value[1] - parent_global[1] - self._anchor_offset[1],
            )
        else:
            self.position = (
                value[0] - self._anchor_offset[0],
                value[1] - self._anchor_offset[1],
            )
    

class Label(Control):
    """Text label control."""

    class TextAlignType(Enum):
        LEFT = "LEFT"
        CENTER = "CENTER"
        RIGHT = "RIGHT"

    def __init__(self) -> None:
        """Create a label with centered text alignment."""
        super().__init__()
        self.text = ""
        self.text_align = self.TextAlignType.CENTER

    def load_data(self, data: dict):
        """Restore label-specific state from serialized data."""
        super().load_data(data)
        if "text_align" in data and isinstance(data["text_align"], str):
            try:
                self.text_align = self.TextAlignType[data["text_align"]]
            except (KeyError, ValueError):
                self.text_align = self.TextAlignType.CENTER
    

class Button(Control):
    """Clickable text button control."""

    def __init__(self) -> None:
        """Create a button with default state."""
        super().__init__()
        self.text = ""
        self.flat = False
        self.pressed = False
        self._text_size_cache: tuple[int, int] | None = None

    def _contains_point(self, point: tuple[float, float]) -> bool:
        """Return whether a point lies inside the button rectangle."""
        x, y = float(self.global_position[0]), float(self.global_position[1])
        w, h = float(self.size[0]), float(self.size[1])
        if w <= 0 or h <= 0:
            return False
        px, py = float(point[0]), float(point[1])
        return x <= px <= (x + w) and y <= py <= (y + h)

    def _input(self, event):
        """Handle pointer input for button press state."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._contains_point(event.pos):
                self.pressed = True
                self.emit_signal("on_pressed")
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.pressed = False

    
    def process_ui(self, viewport_size=None, parent_rect=None, apply_anchor=True):
        """Size the button from text content and then lay it out."""
        size_w, size_h = float(self.size[0]), float(self.size[1])
        if (size_w < 1 or size_h < 1) and self.text:
            text_w, text_h = self._text_size_cache if self._text_size_cache else (0, 0)
            padding = getattr(self, "padding", self.DEFAULT_PADDING)
            button_w = text_w + int(padding[1]) + int(padding[3])
            button_h = text_h + int(padding[0]) + int(padding[2])
            self.size = (float(max(button_w, 40)), float(max(button_h, 24)))
        
        super().process_ui(viewport_size, parent_rect, apply_anchor)
    

class TextureRect2D(Control):
    """UI control that displays a texture resource."""

    def __init__(self) -> None:
        """Create an empty texture rect control."""
        super().__init__()
        self._texture_resource = None

    def save_data(self) -> dict:
        """Serialize the texture rect state."""
        data = super().save_data()
        if self._texture_resource:
            data["texture"] = self._texture_resource
        return data

    def load_data(self, data: dict):
        """Restore texture rect state from serialized data."""
        super().load_data(data)
        if "texture" in data:
            self.texture = data["texture"]

    @property
    def image(self):
        """Return the loaded texture surface or ``None``."""
        if self._texture_resource:
            return self._texture_resource.get_texture()
        return None

    @property
    def texture(self):
        return self._texture_resource

    @texture.setter
    def texture(self, value):
        """Assign a texture resource or resolve one from a file path."""
        if isinstance(value, Resources.Texture2D):
            self._texture_resource = value
        elif isinstance(value, str):
            try:
                res = ResourceServer.ResourceLoader.load(value)
                if isinstance(res, Resources.Texture2D):
                    self._texture_resource = res
                else:
                    self._texture_resource = Resources.Texture2D(resource_path=value)
            except Exception:
                self._texture_resource = None
        else:
            self._texture_resource = None

class VBoxContainer(Control):
    """Vertical container that stacks child controls."""

    def __init__(self) -> None:
        """Create a vertical container with default spacing."""
        super().__init__()

        self.gap = self.DEFAULT_GAP

    def process_ui(self, viewport_size=None, parent_rect=None, apply_anchor=True):
        """Lay out child controls vertically."""
        if apply_anchor:
            self._resolve_anchor(self._layout_parent_rect(viewport_size, parent_rect))

        current_y = 0
        gap = max(0, int(self.gap))
        for idx, child in enumerate(self._children):
            if isinstance(child, Control):
                if idx > 0:
                    current_y += gap
                child.position = (0.0, float(current_y))
                child.process_ui(viewport_size, parent_rect=self._content_rect(), apply_anchor=True)
                current_y += float(getattr(child, "size", (0, 0))[1]) if hasattr(child, "size") else 0.0

class HBoxContainer(Control):
    """Horizontal container that stacks child controls."""

    def __init__(self) -> None:
        """Create a horizontal container with default spacing."""
        super().__init__()
        self.gap = self.DEFAULT_GAP
    def process_ui(self, viewport_size=None, parent_rect=None, apply_anchor=True):
        """Lay out child controls horizontally."""
        if apply_anchor:
            self._resolve_anchor(self._layout_parent_rect(viewport_size, parent_rect))

        current_x = 0
        gap = max(0, int(self.gap))
        for idx, child in enumerate(self._children):
            if isinstance(child, Control):
                if idx > 0:
                    current_x += gap
                child.position = (float(current_x), 0.0)
                child.process_ui(viewport_size, parent_rect=self._content_rect(), apply_anchor=True)
                current_x += float(getattr(child, "size", (0, 0))[0]) if hasattr(child, "size") else 0.0    

class ColorRect2D(Control):
    """Solid-color rectangle control."""

    def __init__(self) -> None:
        """Create a solid color rectangle control."""
        super().__init__()
        self.color : tuple[int, int, int, int] = (255, 255, 255, 255)

class TextureProgress(Control):
    """Progress bar control with separate background and fill textures."""

    def __init__(self) -> None:
        """Create a progress bar control."""
        super().__init__()
        self.value = 0.0
        self.min_value = 0.0
        self.max_value = 100.0
        self._under_texture_resource = None
        self._fill_texture_resource = None

    @property
    def under_texture(self):
        """Return the background texture resource."""
        return self._under_texture_resource
    
    @under_texture.setter
    def under_texture(self, value):
        """Assign the background texture resource or resolve it from a path."""
        if isinstance(value, Resources.Texture2D):
            self._under_texture_resource = value
        elif isinstance(value, str):
            try:
                res = ResourceServer.ResourceLoader.load(value)
                if isinstance(res, Resources.Texture2D):
                    self._under_texture_resource = res
                else:
                    self._under_texture_resource = Resources.Texture2D(resource_path=value)
            except Exception:
                self._under_texture_resource = None
        else:
            self._under_texture_resource = None
    
    @property
    def fill_texture(self):
        """Return the fill texture resource."""
        return self._fill_texture_resource
    
    @fill_texture.setter
    def fill_texture(self, value):
        """Assign the fill texture resource or resolve it from a path."""
        if isinstance(value, Resources.Texture2D):
            self._fill_texture_resource = value
        elif isinstance(value, str):
            try:
                res = ResourceServer.ResourceLoader.load(value)
                if isinstance(res, Resources.Texture2D):
                    self._fill_texture_resource = res
                else:
                    self._fill_texture_resource = Resources.Texture2D(resource_path=value)
            except Exception:
                self._fill_texture_resource = None
        else:
            self._fill_texture_resource = None

    def save_data(self) -> dict:
        data = super().save_data()
        data["under_texture"] = self._under_texture_resource
        data["fill_texture"] = self._fill_texture_resource
        return data

    def load_data(self, data: dict):
        super().load_data(data)
        if "under_texture" in data:
            self.under_texture = data["under_texture"]
        if "fill_texture" in data:
            self.fill_texture = data["fill_texture"]
    

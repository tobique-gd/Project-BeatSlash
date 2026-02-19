import json
import os
import pygame
import importlib
import importlib.util
import os


#resource is a custom data structure that just hase a name and path with a template function for serializing data
class Resource:
    def __init__(self, name: str = "Resource", resource_path: str | None = None):
        self.name = name
        self.resource_path = resource_path
        
    def to_dict(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "name": self.name,
            "resource_path": self.resource_path,
        }

    def save(self, path: str | None = None):
        if path:
            self.resource_path = path
        
        if not self.resource_path:
            print(f"Error: Cannot save {self.name}, no path specified.")
            return

        try:
            with open(self.resource_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=4)
        except Exception as e:
            print(f"Error saving resource {self.name} to {self.resource_path}: {e}")

#audio preloading loading with pygame mixer
class AudioResource(Resource):
    def __init__(self, name: str = "Audio", file_path: str | None = None):
        super().__init__(name=name, resource_path=file_path)
        self.file_path = file_path
        self._sound = None
        
        if file_path:
            self.load_audio(file_path)

    def load_audio(self, path: str):
        self.file_path = path
        self.resource_path = path
        try:
            self._sound = pygame.mixer.Sound(path)
        except Exception as e:
            print(f"Failed to load audio from {path}: {e}")
            self._sound = None

    def get_sound(self):
        if not self._sound and self.file_path:
            self.load_audio(self.file_path)
        return self._sound

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["file_path"] = self.file_path
        return data

class ScriptResource(Resource):
    def __init__(self, name="Script", script_path: str | None = None):
        super().__init__(name=name)
        self.script_path = script_path
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["script_path"] = self.script_path
        return data

#texture resources load textures into alpha converted textures so we can have transparent backgrounds
class TextureResource(Resource):
    def __init__(self, name="Texture", resource_path: str | None = None):
        super().__init__(name=name, resource_path=resource_path)
        self.texture_path = resource_path
        self._surface = None

        if resource_path:
            self.load_texture(resource_path)
    
    def load_texture(self, path: str):
        self.texture_path = path
        self.resource_path = path
        try:
            self._surface = pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"Failed to load texture from {path}: {e}")
            self._surface = None

    def get_texture(self):
        if not self._surface and self.texture_path:
            self.load_texture(self.texture_path)
        return self._surface

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["texture_path"] = self.texture_path
        return data

#TODO i dont like the way im handling this for now so i may need to redo how collision shape resources work
class CollisionShape(Resource):
    def __init__(self, name="CollisionShape", resource_path=None):
        super().__init__(name, resource_path)

class CollisionRectangleShape(CollisionShape):
    def __init__(self, size: tuple[float, float], resource_path: str | None = None):
        super().__init__(name="Rectangle", resource_path=resource_path)
        self.size = size
    
    def to_dict(self):
        data = super().to_dict()
        data["size"] = self.size
        return data


class CollisionCircleShape(CollisionShape):
    def __init__(self, radius: float, resource_path: str | None = None):
        super().__init__(name="Circle", resource_path=resource_path)
        self.radius = radius

    def to_dict(self):
        data = super().to_dict()
        data["radius"] = self.radius
        return data

class CollisionPolygonShape(CollisionShape):
    def __init__(self, points: list[tuple[float, float]], resource_path: str | None = None):
        super().__init__(name="Polygon", resource_path=resource_path)
        self.points = points

    def to_dict(self):
        data = super().to_dict()
        data["points"] = self.points
        return data

class CollisionShapeType:
    RECTANGLE = CollisionRectangleShape(size=(0, 0))
    CIRCLE = CollisionCircleShape(radius=0)
    POLYGON = CollisionPolygonShape(points=[])



#script proxy for handling runtime loading of scripts to be executed on nodes
class ScriptProxy:
    def __init__(self, node, script_path: str):
        self.node = node
        self._script_path = script_path
        self._module = _load_module_from_path(script_path)

    def _call(self, name: str, *args):
        fn = getattr(self._module, name, None)
        if callable(fn):
            return fn(self, *args)
        return None

    def _ready(self):
        return self._call("_ready")

    def _process(self, delta):
        return self._call("_process", delta)

    def _input(self, event):
        return self._call("_input", event)

    def __getattr__(self, name):
        module = object.__getattribute__(self, "_module")
        if hasattr(module, name):
            return getattr(module, name)
        raise AttributeError(name)

#helper functions for file management

def _is_file_path(path: str) -> bool:
    return path.endswith('.py') or os.path.sep in path or (os.name == 'nt' and ':' in path)


def _path_to_module_name(file_path: str) -> tuple[str, str]:
    abs_path = os.path.abspath(file_path)
    
    current = os.path.dirname(abs_path)
    package_root = None
    
    while current != os.path.dirname(current):
        parent = os.path.dirname(current)
        if not os.path.exists(os.path.join(parent, '__init__.py')):
            package_root = current
            break
        current = parent
    
    if package_root is None:
        package_root = os.path.dirname(abs_path)
    
    rel_path = os.path.relpath(abs_path, package_root)
    module_name = rel_path.replace(os.sep, '.').replace('.py', '')
    
    return module_name, package_root


def _load_module_from_path(script_path: str):
    if _is_file_path(script_path):
        resolved_path = script_path
        try:
            from .ResourceServer import ResourceLoader
            resolved_path = ResourceLoader.resolve_path(script_path)
        except Exception:
            resolved_path = script_path

        abs_path = os.path.abspath(resolved_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Script file not found: {abs_path}")
        
        import sys
        
        module_name, package_root = _path_to_module_name(abs_path)
        
        if package_root not in sys.path:
            sys.path.insert(0, package_root)
        
        try:
            return importlib.import_module(module_name)
        finally:
            if package_root in sys.path:
                sys.path.remove(package_root)
    else:
        return importlib.import_module(script_path)


def _resolve_script_class(module):
    script_cls = getattr(module, "SCRIPT_CLASS", None) or getattr(module, "__script_class__", None)
    if isinstance(script_cls, str):
        script_cls = getattr(module, script_cls, None)
    if isinstance(script_cls, type):
        return script_cls
    return None


def load_script(script_path: str, node):
    module = _load_module_from_path(script_path)
    script_cls = _resolve_script_class(module)
    if script_cls:
        return script_cls(node)
    return ScriptProxy(node, script_path)


def get_script_path(script) -> str | None:
    if isinstance(script, str):
        return script
    if hasattr(script, "_script_path"):
        return getattr(script, "_script_path")
    if hasattr(script, "_module_name"):
        return getattr(script, "_module_name")
    module = getattr(script, "__class__", None)
    if module:
        return getattr(module, "__module__", None)
    return None
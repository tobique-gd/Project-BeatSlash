import json
import os
import pygame
import importlib
import importlib.util
import os
from . import ErrorHandler


def _coerce_int_pair(value, fallback=(0, 0)):
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return (int(value[0]), int(value[1]))
        except Exception:
            return fallback
    return fallback


def _coerce_texture_region(value, fallback=((0, 0), (16, 16))):
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        origin = _coerce_int_pair(value[0], fallback[0])
        size = _coerce_int_pair(value[1], fallback[1])
        return (origin, size)
    return fallback


#resource is a custom data structure that just hase a name and path with a template function for serializing data
class Resource:
    type_id = "Resource"
    extensions: tuple[str, ...] = ()
    _type_registry: dict[str, type] = {}
    _extension_registry: dict[str, type] = {}
    _resource_marker = "__resource__"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is Resource:
            return

        type_id = str(getattr(cls, "type_id", cls.__name__))
        Resource._type_registry[type_id] = cls
        Resource._type_registry[cls.__name__] = cls

        for ext in getattr(cls, "extensions", ()):
            if isinstance(ext, str) and ext:
                Resource._extension_registry[ext.lower()] = cls

    def __init__(self, name: str = "Resource", resource_path: str | None = None):
        self.name = name
        self.resource_path = resource_path

    @classmethod
    def class_for_extension(cls, extension: str):
        if not isinstance(extension, str):
            return None
        return cls._extension_registry.get(extension.lower())

    @classmethod
    def class_for_type(cls, type_name: str):
        if not isinstance(type_name, str):
            return None
        return cls._type_registry.get(type_name)

    @classmethod
    def from_path(cls, path: str):
        return cls(resource_path=path)

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            return None

        resource_type = data.get("resource_type") or data.get("type")
        target_cls = cls.class_for_type(resource_type) if resource_type else cls
        if target_cls is None:
            target_cls = cls

        if target_cls is not cls:
            return target_cls.from_dict(data)

        obj = cls(
            name=data.get("name", "Resource"),
            resource_path=data.get("resource_path"),
        )
        obj.load_data(data)
        return obj
        
    def to_dict(self) -> dict:
        data = self.save_data()
        data["type"] = self.__class__.__name__
        data["resource_type"] = getattr(self, "type_id", self.__class__.__name__)
        return data

    @classmethod
    def encode_value(cls, value):
        if isinstance(value, Resource):
            return {cls._resource_marker: value.to_dict()}

        if isinstance(value, tuple):
            return [cls.encode_value(item) for item in value]

        if isinstance(value, list):
            return [cls.encode_value(item) for item in value]

        if isinstance(value, dict):
            return {str(key): cls.encode_value(item) for key, item in value.items()}

        return value

    @classmethod
    def decode_value(cls, value):
        if isinstance(value, dict):
            payload = value.get(cls._resource_marker)
            if isinstance(payload, dict):
                # Decode using the payload's declared resource type, not the caller class.
                return Resource.from_dict(payload)
            return {key: cls.decode_value(item) for key, item in value.items()}

        if isinstance(value, list):
            return [cls.decode_value(item) for item in value]

        return value

    def save_data(self) -> dict:
        return {
            "name": self.name,
            "resource_path": self.resource_path,
        }

    def load_data(self, data: dict):
        self.name = data.get("name", self.name)
        self.resource_path = data.get("resource_path", self.resource_path)

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

#audio preloading, loading with pygame mixer
class AudioStream(Resource):
    type_id = "AudioStream"
    extensions = (".mp3", ".wav", ".ogg")

    def __init__(self, name: str = "Audio", resource_path: str | None = None):
        super().__init__(name=name, resource_path=resource_path)
        self.file_path = resource_path
        self._sound = None
        
        if resource_path:
            self.load_audio(resource_path)

    def load_audio(self, path: str):
        self.file_path = path
        self.resource_path = path
        try:
            self._sound = pygame.mixer.Sound(path)
        except Exception as e:
            print(f"Failed to load audio from {path}: {e}")
            self._sound = None

    def get_sound(self):
        if not self._sound and self.resource_path:
            self.load_audio(self.resource_path)
        return self._sound

    def save_data(self) -> dict:
        data = super().save_data()
        data["file_path"] = self.resource_path
        return data

    def load_data(self, data: dict):
         super().load_data(data)
         path = data.get("file_path") or data.get("resource_path")
         if path:
             self.load_audio(path)

    @classmethod
    def from_path(cls, path: str):
        return cls(resource_path=path)

    @classmethod
    def from_dict(cls, data: dict):
        return super().from_dict(data)

class Script(Resource):
    type_id = "Script"
    extensions = (".py",)

    def __init__(self, name="Script", resource_path: str | None = None):
        super().__init__(name=name, resource_path=resource_path)
        self.script_path = resource_path
    
    def save_data(self) -> dict:
        data = super().save_data()
        data["script_path"] = self.resource_path
        return data

    def load_data(self, data: dict):
        super().load_data(data)
        path = data.get("script_path") or data.get("resource_path")
        if path:
            self.script_path = path

    @classmethod
    def from_path(cls, path: str):
        return cls(resource_path=path)

    @classmethod
    def from_dict(cls, data: dict):
        return super().from_dict(data)

#texture resources load textures into alpha converted textures so we can have transparent backgrounds
class Texture2D(Resource):
    type_id = "Texture2D"
    extensions = (".png", ".jpg", ".jpeg", ".bmp")

    def __init__(self, name="Texture", resource_path: str | None = None):
        super().__init__(name=name, resource_path=resource_path)
        self.texture_path = resource_path
        self._surface = None

        if resource_path:
            self.load_texture(resource_path)
    
    def get_width(self):
        if self._surface:
            return self._surface.get_width()
        return 0

    def get_height(self):
        if self._surface:
            return self._surface.get_height()
        return 0

    def load_texture(self, path: str):
        self.texture_path = path
        self.resource_path = path
        try:
            self._surface = pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"Failed to load texture from {path}: {e}")
            self._surface = None

    def get_texture(self):
        if not self._surface and self.resource_path:
            self.load_texture(self.resource_path)
        return self._surface

    def save_data(self) -> dict:
        data = super().save_data()
        data["texture_path"] = self.resource_path
        return data

    def load_data(self, data: dict):
        super().load_data(data)
        path = data.get("texture_path") or data.get("resource_path")
        if path:
            self.load_texture(path)

    @classmethod
    def from_path(cls, path: str):
        return cls(resource_path=path)

    @classmethod
    def from_dict(cls, data: dict):
        return super().from_dict(data)

class CollisionShape(Resource):
    type_id = "CollisionShape"

    def __init__(self, name="CollisionShape", resource_path=None):
        super().__init__(name, resource_path)

class CollisionRectangleShape(CollisionShape):
    type_id = "CollisionRectangleShape"

    def __init__(self, size: tuple[float, float] = (32, 32), resource_path: str | None = None):
        super().__init__(name="Rectangle", resource_path=resource_path)
        self.size = size
    
    def save_data(self):
        data = super().save_data()
        data["size"] = self.size
        return data

    def load_data(self, data: dict):
        super().load_data(data)
        if "size" in data:
             sz = data["size"]
             if isinstance(sz, list):
                 sz = tuple(sz)
             self.size = sz

    @classmethod
    def from_dict(cls, data: dict):
        return super().from_dict(data)



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



#sprite animation is a resource that manages animations in the AnimatedSprite2D
#it precomputes all surfaces and stores them in an array for fast O(1) look up when looping through the animation
class SpriteAnimation(Resource):
    type_id = "SpriteAnimation"
    extensions = (".anim", ".json")

    def __init__(self, name="Animation", spritesheet=None, frame_size: tuple[int,int]=(0,0), frames: int=0, _loop: bool=True, fps: int = 12, resource_path: str | None = None):
        super().__init__(name=name, resource_path=resource_path)
        self.frames_surfaces = []
        self.frames_local_rects = []
        
        self.spritesheet = None
        self.spritesheet_path = None

        if isinstance(spritesheet, str):
            self.spritesheet = Texture2D(resource_path=spritesheet)
            self.spritesheet_path = spritesheet
        elif isinstance(spritesheet, Texture2D):
            self.spritesheet = spritesheet
            if spritesheet.resource_path:
                 self.spritesheet_path = spritesheet.resource_path

        self.frame_size = frame_size
        self.frames = frames
        self.frame_regions: list[tuple[tuple[int, int], tuple[int, int]]] = []
        self.fps = fps
        self.loop = _loop
        
        self.current_frame = 0
        self.time_accumulator = 0.0
        self.finished = False

        self.reload()

    def _normalized_frame_regions(self):
        normalized: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for item in self.frame_regions:
            region = _coerce_texture_region(item, fallback=((0, 0), _coerce_int_pair(self.frame_size, (0, 0))))
            (x, y), (w, h) = region
            if w <= 0 or h <= 0:
                continue
            normalized.append(((int(x), int(y)), (int(w), int(h))))
        return normalized

    def reload(self):
        spritesheet_surface = None
        if self.spritesheet:
            spritesheet_surface = self.spritesheet.get_texture()
        elif self.spritesheet_path:
             self.spritesheet = Texture2D(resource_path=self.spritesheet_path)
             spritesheet_surface = self.spritesheet.get_texture()

        self.frames_surfaces = []
        self.frames_local_rects = []

        if spritesheet_surface:
             sheet_width = spritesheet_surface.get_width()
             sheet_height = spritesheet_surface.get_height()

             explicit_regions = self._normalized_frame_regions()
             if explicit_regions:
                 self.frame_regions = explicit_regions
                 self.frames = len(explicit_regions)
                 for i, region in enumerate(explicit_regions):
                     (x, y), (w, h) = region
                     if x < 0 or y < 0:
                         continue
                     if x + w > sheet_width or y + h > sheet_height:
                         continue
                     rect = pygame.Rect(x, y, w, h)
                     try:
                         surface = spritesheet_surface.subsurface(rect).copy()
                         self.frames_surfaces.append(surface)
                         sw, sh = surface.get_size()
                         self.frames_local_rects.append(((-sw / 2, -sh / 2), (sw, sh)))
                     except Exception as e:
                         print(f"Error processing explicit frame {i} of {self.name}: {e}")
             else:
                 frame_w, frame_h = _coerce_int_pair(self.frame_size, (0, 0))
                 if frame_w <= 0 or frame_h <= 0:
                     self.frames = 0
                     return

                 for i in range(self.frames):
                     x = (i * frame_w) % sheet_width
                     y = ((i * frame_w) // sheet_width) * frame_h

                     if x + frame_w > sheet_width or y + frame_h > sheet_height:
                         continue

                     rect = pygame.Rect(x, y, frame_w, frame_h)
                     try:
                         surface = spritesheet_surface.subsurface(rect).copy()
                         self.frames_surfaces.append(surface)
                         w, h = surface.get_size()
                         self.frames_local_rects.append(((-w / 2, -h / 2), (w, h)))
                     except Exception as e:
                         print(f"Error processing frame {i} of {self.name}: {e}")

    def update(self, delta: float):
        if self.finished or self.frames == 0 or not self.frames_surfaces:
            return

        self.time_accumulator += delta
        frame_time = 1.0 / self.fps

        while self.time_accumulator >= frame_time:
            self.current_frame += 1
            self.time_accumulator -= frame_time

            if self.current_frame >= self.frames:
                if self.loop:
                    self.current_frame = 0
                else:
                    self.current_frame = self.frames - 1
                    self.finished = True
                    break

    def get_current_frame_rect(self) -> pygame.Rect:
        if not self.spritesheet:
            return pygame.Rect(0, 0, 0, 0)
        
        tex = self.spritesheet.get_texture()
        if not tex:
            return pygame.Rect(0, 0, 0, 0)

        if self.frame_regions:
            frame_index = int(max(0, min(self.current_frame, len(self.frame_regions) - 1)))
            (x, y), (w, h) = self.frame_regions[frame_index]
            return pygame.Rect(int(x), int(y), int(w), int(h))

        sheet_width = tex.get_width()
        frame_x = (self.current_frame * self.frame_size[0]) % sheet_width
        frame_y = ((self.current_frame * self.frame_size[0]) // sheet_width) * self.frame_size[1]
        return pygame.Rect(frame_x, frame_y, *self.frame_size)

    def save_data(self) -> dict:
        data = super().save_data()
        
        ss_path = None
        if self.spritesheet:
            ss_path = self.spritesheet.resource_path
            
        data.update({
            "spritesheet": self.spritesheet, 
            "frame_size": self.frame_size,
            "frames": self.frames,
            "frame_regions": [
                [[int(region[0][0]), int(region[0][1])], [int(region[1][0]), int(region[1][1])]]
                for region in self._normalized_frame_regions()
            ],
            "fps": self.fps,
            "loop": self.loop
        })
        return data

    def load_data(self, data: dict):
        super().load_data(data)
   
        path_val = data.get("spritesheet_path")
        if path_val:
            self.spritesheet_path = path_val

        ss_val = data.get("spritesheet")
        
        if isinstance(ss_val, Texture2D):
             self.spritesheet = ss_val
             if ss_val.resource_path:
                 self.spritesheet_path = ss_val.resource_path
        elif isinstance(ss_val, str):
             self.spritesheet_path = ss_val
             self.spritesheet = Texture2D(resource_path=ss_val)
        elif self.spritesheet_path:
             if not self.spritesheet:
                  self.spritesheet = Texture2D(resource_path=self.spritesheet_path)

        frame_size_raw = data.get("frame_size", self.frame_size)
        if isinstance(frame_size_raw, list):
            self.frame_size = tuple(frame_size_raw)
        else:
            self.frame_size = frame_size_raw

        self.frames = int(data.get("frames", self.frames))
        raw_regions = data.get("frame_regions", self.frame_regions)
        if isinstance(raw_regions, list):
            self.frame_regions = []
            for item in raw_regions:
                region = _coerce_texture_region(item, fallback=((0, 0), _coerce_int_pair(self.frame_size, (0, 0))))
                (x, y), (w, h) = region
                if w <= 0 or h <= 0:
                    continue
                self.frame_regions.append(((int(x), int(y)), (int(w), int(h))))
        self.fps = int(data.get("fps", self.fps))
        self.loop = bool(data.get("loop", self.loop))

        self.reload()

    @classmethod
    def from_path(cls, path: str):
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                obj = cls.from_dict(data)
                obj.resource_path = path
                return obj
            except Exception as e:
                print(f"Failed to load animation from {path}: {e}")
        return cls(resource_path=path)

    @classmethod
    def from_dict(cls, data: dict):
        obj = cls(
            name=data.get("name", "Animation"),
            resource_path=data.get("resource_path")
        )
        obj.load_data(data)
        return obj

class Tileset2D(Resource):
    type_id = "Tileset"
    extensions = (".tileset", ".json")

    def __init__(self, name="Tileset", resource_path: str | None = None):
        super().__init__(name=name, resource_path=resource_path)
        self.tile_size = (16, 16)
        self.tilesheet : Texture2D | None = None
        self.tiles = [Tile2D(0)]
        self._tile_surface_cache: dict[int, pygame.Surface] = {}

    def clear_runtime_cache(self):
        self._tile_surface_cache = {}

    def ensure_default_tile(self):
        if not isinstance(self.tiles, list):
            self.tiles = []

        valid_tiles = [tile for tile in self.tiles if isinstance(tile, Tile2D)]
        if not valid_tiles:
            valid_tiles = [Tile2D(0)]

        valid_tiles.sort(key=lambda tile: tile.id)
        self.tiles = valid_tiles

    def next_available_tile_id(self) -> int:
        self.ensure_default_tile()
        existing_ids = {tile.id for tile in self.tiles}
        new_id = 0
        while new_id in existing_ids:
            new_id += 1
        return new_id

    def get_tile_by_id(self, tile_id: int):
        self.ensure_default_tile()
        for tile in self.tiles:
            if tile.id == tile_id:
                return tile
        return None

    def add_tile(self, tile=None):
        self.ensure_default_tile()
        if tile is None:
            tile = Tile2D(self.next_available_tile_id())
            tile.texture_region = ((0, 0), _coerce_int_pair(self.tile_size, (16, 16)))

        if not isinstance(tile, Tile2D):
            return None

        duplicate = self.get_tile_by_id(tile.id)
        if duplicate is not None and duplicate is not tile:
            tile.id = self.next_available_tile_id()

        self.tiles.append(tile)
        self.tiles.sort(key=lambda item: item.id)
        self.clear_runtime_cache()
        return tile

    def remove_tile(self, tile_id: int):
        self.ensure_default_tile()
        self.tiles = [tile for tile in self.tiles if tile.id != tile_id]
        if not self.tiles:
            self.tiles = [Tile2D(0)]
        self.clear_runtime_cache()

    def get_tile_surface(self, tile_id: int):
        if tile_id in self._tile_surface_cache:
            return self._tile_surface_cache[tile_id]

        tile = self.get_tile_by_id(tile_id)
        if tile is None:
            return None

        if self.tilesheet is None and self.resource_path:
            pass

        sheet_surface = self.tilesheet.get_texture() if isinstance(self.tilesheet, Texture2D) else None
        if sheet_surface is None:
            return None

        (origin_x, origin_y), (size_x, size_y) = _coerce_texture_region(tile.texture_region)
        if size_x <= 0 or size_y <= 0:
            return None

        rect = pygame.Rect(origin_x, origin_y, size_x, size_y)
        if rect.right > sheet_surface.get_width() or rect.bottom > sheet_surface.get_height():
            return None

        try:
            surface = sheet_surface.subsurface(rect).copy()
        except Exception:
            return None

        self._tile_surface_cache[tile_id] = surface
        return surface

    def save_data(self) -> dict:
        self.ensure_default_tile()
        data = super().save_data()
        data["tile_size"] = list(_coerce_int_pair(self.tile_size, (16, 16)))
        data["tilesheet"] = self.encode_value(self.tilesheet)
        data["tilesheet_path"] = self.tilesheet.resource_path if isinstance(self.tilesheet, Texture2D) else None
        data["tiles"] = [self.encode_value(tile) for tile in self.tiles]
        return data

    def load_data(self, data: dict):
        super().load_data(data)
        self.tile_size = _coerce_int_pair(data.get("tile_size"), self.tile_size)

        tilesheet_value = data.get("tilesheet")
        if tilesheet_value is not None:
            tilesheet_value = self.decode_value(tilesheet_value)

        if isinstance(tilesheet_value, Texture2D):
            self.tilesheet = tilesheet_value
        else:
            tilesheet_path = data.get("tilesheet_path")
            if isinstance(tilesheet_value, str):
                tilesheet_path = tilesheet_value

            if isinstance(tilesheet_path, str) and tilesheet_path:
                self.tilesheet = Texture2D(resource_path=tilesheet_path)
            else:
                self.tilesheet = None

        loaded_tiles = []
        for item in data.get("tiles", []):
            decoded = self.decode_value(item)
            if isinstance(decoded, Tile2D):
                loaded_tiles.append(decoded)
            elif isinstance(decoded, dict):
                tile = Tile2D(0)
                tile.load_data(decoded)
                loaded_tiles.append(tile)

        self.tiles = loaded_tiles or [Tile2D(0)]
        self.ensure_default_tile()
        self.clear_runtime_cache()

    @classmethod
    def from_path(cls, path: str):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                obj = cls.from_dict(data)
                if obj is not None:
                    obj.resource_path = path
                    return obj
            except Exception as e:
                print(f"Failed to load tileset from {path}: {e}")
        return cls(resource_path=path)

    @classmethod
    def from_dict(cls, data: dict):
        obj = cls(
            name=data.get("name", "Tileset"),
            resource_path=data.get("resource_path")
        )
        obj.load_data(data)
        return obj

class Tile2D(Resource):
    type_id = "Tile"

    def __init__(self, id: int, name="Tile", resource_path: str | None = None):
        super().__init__(name=name, resource_path=resource_path)
        self.texture_region: tuple[tuple[int, int], tuple[int, int]] = ((0, 0), (16, 16))
        self.collision_shape: CollisionShape | None = None
        self.id = id

    def save_data(self) -> dict:
        data = super().save_data()
        data["id"] = int(self.id)
        data["texture_region"] = self.encode_value(self.texture_region)
        data["collision_shape"] = self.encode_value(self.collision_shape)
        return data

    def load_data(self, data: dict):
        super().load_data(data)
        self.id = int(data.get("id", self.id))
        self.texture_region = _coerce_texture_region(data.get("texture_region"), self.texture_region)

        collision_shape = data.get("collision_shape")
        if collision_shape is not None:
            collision_shape = self.decode_value(collision_shape)
        self.collision_shape = collision_shape if isinstance(collision_shape, CollisionShape) else None

    @classmethod
    def from_dict(cls, data: dict):
        obj = cls(
            id=int(data.get("id", 0)),
            name=data.get("name", "Tile"),
            resource_path=data.get("resource_path")
        )
        obj.load_data(data)
        return obj

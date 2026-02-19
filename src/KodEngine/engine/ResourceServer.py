import json
import os
from . import (Nodes, NodeComponents, Scenes, Resources)
from .ErrorHandler import ErrorHandler

#ResourceLoader handles caching, loading and saving resources liek audio, textures
#might need to redo this to be extendable easily and i wont have to manually define acceptable formats its just a little hacky
class ResourceLoader:
    _cache = {}
    _project_root = None

    @staticmethod
    def set_project_root(path: str):
        ResourceLoader._project_root = os.path.abspath(path)

    @staticmethod
    def resolve_path(path: str):
        # Helper to resolve path without loading
        if not os.path.isabs(path) and ResourceLoader._project_root:
             potential_path = os.path.join(ResourceLoader._project_root, path)
             if os.path.exists(potential_path):
                 return potential_path
        return path

    @staticmethod
    def load(path: str):
        path = ResourceLoader.resolve_path(path)
        path = os.path.abspath(path)
        if path in ResourceLoader._cache:
            return ResourceLoader._cache[path]

        if not os.path.exists(path):
            ErrorHandler.throw_warning(f"Resource file not found: {path}")
            return None

        _, ext = os.path.splitext(path)
        
        #audio
        if ext.lower() in ['.mp3', '.wav', '.ogg']:
            res = Resources.AudioResource(file_path=path)
            ResourceLoader._cache[path] = res
            return res
        
        #textures
        if ext.lower() in ['.png', '.jpg', '.jpeg', '.bmp']:
            res = Resources.TextureResource(resource_path=path)
            ResourceLoader._cache[path] = res
            return res

        return None

#SceneLoader handles saving and loading scenes
# its structured as staticmethods to allow for clean calling of the load and save functions 
class SceneLoader:
    def __init__(self) -> None:
        pass

    @staticmethod
    def _warn(message: str):
        ErrorHandler.throw_warning(message)

    @staticmethod
    def _error(message: str):
        ErrorHandler.throw_error(message)

    @staticmethod
    def _to_project_relative(path: str):
        if not isinstance(path, str) or not path:
            return path

        project_root = getattr(ResourceLoader, "_project_root", None)
        if not project_root:
            return path

        try:
            abs_path = os.path.abspath(path)
            root = os.path.abspath(project_root)
            if os.path.commonpath([abs_path, root]) == root:
                return os.path.relpath(abs_path, root)
        except Exception:
            return path

        return path

    #reading scene files (.kscn) that are basically json
    @staticmethod
    def _read_json(file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            SceneLoader._error(f"Scene file not found: '{file_path}'")
        except json.JSONDecodeError as e:
            SceneLoader._error(f"Invalid JSON in scene file '{file_path}': {e}")
        except Exception as e:
            SceneLoader._error(f"Failed to read scene file '{file_path}': {e}")
        return None

    @staticmethod
    def _write_json(file_path, data):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, default=str, indent=2)
            return True
        except Exception as e:
            SceneLoader._error(f"Failed to write scene to '{file_path}': {e}")
            return False

    @staticmethod
    def _safe_set_attr(node, key, value) -> bool:
        try:
            setattr(node, key, value)
            return True
        except AttributeError as e:
            SceneLoader._warn(f"Node '{type(node).__name__}' has no attribute '{key}': {e}")
        except ValueError as e:
            SceneLoader._warn(f"Invalid value for '{key}' on node '{type(node).__name__}': {e}")
        except Exception as e:
            SceneLoader._warn(f"Failed to set property '{key}' on node '{type(node).__name__}': {e}")
        return False


    @staticmethod
    def _apply_audio_path(node, value):
        if not hasattr(node, "audio"):
            return
        try:
            node.audio = value
        except Exception as e:
            SceneLoader._warn(f"Failed to set audio from path '{value}': {e}")
            if not SceneLoader._safe_set_attr(node, "audio_path", value):
                SceneLoader._warn(f"Failed to set audio_path '{value}'")

    @staticmethod
    def _apply_texture_path(node, value):
        if not hasattr(node, "texture"):
            return
        try:
            node.texture = value
        except Exception as e:
            SceneLoader._warn(f"Failed to load texture from path '{value}': {e}")
            if not SceneLoader._safe_set_attr(node, "texture_path", str(value)):
                SceneLoader._warn(f"Failed to set texture_path '{value}'")

    @staticmethod
    def _apply_animations(node, animations_meta):
        try:
            from . import NodeComponents as NC
        except Exception as e:
            SceneLoader._warn(f"Failed to import NodeComponents for animations: {e}")
            return

        if not (NC and isinstance(animations_meta, (list, tuple)) and hasattr(node, "add_animation")):
            return

        for anim_meta in animations_meta:
            if isinstance(anim_meta, str):
                try:
                    res = ResourceLoader.load(anim_meta)
                    if res and isinstance(res, NC.SpriteAnimation):
                        node.add_animation(res)
                except Exception as e:
                    SceneLoader._warn(f"Failed to load animation resource '{anim_meta}': {e}")
                continue

            try:
                name = anim_meta.get("name")
                frame_size = tuple(anim_meta.get("frame_size"))
                frames = anim_meta.get("frames")
                fps = anim_meta.get("fps", 12)
                loop = anim_meta.get("loop", True)
                spritesheet_path = anim_meta.get("spritesheet_path")

                if spritesheet_path:
                    # Resolve path using ResourceLoader settings
                    resolved_path = ResourceLoader.resolve_path(spritesheet_path)
                    anim = NC.SpriteAnimation(name, resolved_path, frame_size, frames, loop, fps)
                    node.add_animation(anim)
            except Exception as e:
                SceneLoader._warn(f"Failed to create animation '{anim_meta.get('name', 'unknown')}': {e}")

    @staticmethod
    def save(save_data, file_path):
        try:
            data = SceneLoader.serialize_scene(save_data)
        except Exception as e:
            SceneLoader._error(f"Failed to serialize scene: {e}")
            return False
        if hasattr(save_data, 'path'):
            save_data.path = file_path
        return SceneLoader._write_json(str(file_path), data)

    
    @staticmethod
    def load(file_path):
        data = SceneLoader._read_json(file_path)
        if data is None:
            return None
        
        try:
            scene = SceneLoader.deserialize_scene(data)
            if scene and hasattr(scene, 'path'):
                scene.path = file_path
            return scene
        except Exception as e:
            SceneLoader._error(f"Failed to deserialize scene from '{file_path}': {e}")
            return None
        
    #deserialization of saved scene on disk
    @staticmethod
    def deserialize_scene(scene):
        if not isinstance(scene, dict) or "root" not in scene:
            return None

        def to_primitive(val):
            if isinstance(val, str):
                if (val.startswith("/") or val.startswith("\\") or ":" in val or 
                    val.lower().endswith(('.mp3', '.wav', '.ogg'))):
                    try:
                        res = ResourceLoader.load(val)
                        if res:
                            return res
                    except Exception:
                        pass
                return val

            if isinstance(val, list):
                return tuple(val)
            if isinstance(val, dict) and "__type__" in val:
                t = val["__type__"]
                if t == "CollisionRectangleShape":
                    return Resources.CollisionRectangleShape(size=tuple(val.get("size", (0,0))))
                if t == "CollisionCircleShape":
                    return Resources.CollisionCircleShape(radius=val.get("radius", 0))
                if t == "CollisionPolygonShape":
                    return Resources.CollisionPolygonShape(points=val.get("points", []))
            return val


        def build_node(node_data):
            tname = node_data.get("type")
            cls = getattr(Nodes, tname, getattr(Nodes, "Node", None))
            if cls is None:
                raise RuntimeError(f"Unknown node class: {tname}")

            node = cls()
            try:
                node.name = node_data.get("name", node.name)
            except Exception as e:
                SceneLoader._warn(f"Failed to set node name: {e}")

            props = node_data.get("properties", {})
            script_name = None
            current_animation_meta = None
            for k, v in props.items():
                if k == "script":
                    script_name = v
                    try:
                        node.script = v
                    except Exception:
                        pass
                    continue
                if k == "current_animation":
                    current_animation_meta = v
                    continue
                value = to_primitive(v)
                if k == "animations":
                    SceneLoader._warn("Animations usage cannot be set directly from dict")
                    SceneLoader._apply_animations(node, v)
                    continue

                if SceneLoader._safe_set_attr(node, k, value):
                    continue

                if k == "audio_path":
            
                    SceneLoader._apply_audio_path(node, value)
                elif k == "texture_path":
                    SceneLoader._apply_texture_path(node, value)
        
            
            if current_animation_meta and hasattr(node, "play"):
                try:
                    animation_name = current_animation_meta.get("name")
                    if animation_name:
                        node.play(animation_name)
                        
                        current_frame = current_animation_meta.get("current_frame")
                        if current_frame is not None and node.current_animation:
                            node.current_animation.current_frame = int(current_frame)
                except Exception as e:
                    SceneLoader._error(f"Error restoring animation: {e}")

            for child_data in node_data.get("children", []):
                try:
                    child = build_node(child_data)
                    node.add_child(child)
                except Exception as e:
                    SceneLoader._warn(f"Failed to add child using add_child(), trying direct append: {e}")
                    try:
                        child = build_node(child_data)
                        child._parent = node
                        node._children.append(child)
                    except Exception as e2:
                        SceneLoader._error(f"Failed to add child node '{child_data.get('type', 'unknown')}': {e2}")

            if script_name:
                try:
                    node.runtime_script = Resources.load_script(script_name, node)
                except Exception as e:
                    SceneLoader._warn(f"Failed to load script '{script_name}': {e}")
            return node

        root_node = build_node(scene.get("root"))
        if Scenes.Scene is not None:
            return Scenes.Scene(scene.get("name"), root_node)
        return root_node

    #serialization of scenes into json, we need to extract all data from resources like paths and such to save into a text format
    @staticmethod
    def serialize_scene(scene):
        def is_primitive(v):
            return isinstance(v, (str, int, float, bool)) or v is None

        def normalize_path(v):
            if not isinstance(v, str):
                return v
            return SceneLoader._to_project_relative(v)

        def serialize_value(v):
            if isinstance(v, Resources.Resource) and v.resource_path:
                return normalize_path(v.resource_path)

            if is_primitive(v):
                return normalize_path(v)
            if isinstance(v, (list, tuple)):
                out = []
                for e in v:
                    if is_primitive(e):
                        out.append(e)
                    else:
                        return None
                return out
            if isinstance(v, dict):
                d = {}
                for k, val in v.items():
                    if is_primitive(val):
                        d[k] = val
                return d
            
            try:
                if isinstance(v, Resources.CollisionRectangleShape):
                    return {"__type__": "CollisionRectangleShape", "size": list(v.size)}
                if isinstance(v, Resources.CollisionCircleShape):
                    return {"__type__": "CollisionCircleShape", "radius": v.radius}
                if isinstance(v, Resources.CollisionPolygonShape):
                    return {"__type__": "CollisionPolygonShape", "points": list(v.points)}
            except Exception:
                pass

            return None

        def serialize_node(node):
            node_dict = {
                "type": type(node).__name__,
                "properties": {},
                "children": []
            }

            for attr, val in vars(node).items():
                if attr.startswith("_"):
                    continue
                if attr in ("_children", "_parent", "script", "runtime_script"):
                    continue
                if callable(val):
                    continue

                serialized = serialize_value(val)
                if serialized is not None:
                    node_dict["properties"][attr] = serialized
                else:
                    if attr == "current_animation" and val is not None:
                        try:
                            node_dict["properties"]["current_animation"] = {
                                "name": getattr(val, "name", None),
                                "current_frame": getattr(val, "current_frame", None),
                                "time_accumulator": getattr(val, "time_accumulator", None)
                            }
                            continue
                        except Exception as e:
                            SceneLoader._warn(f"Failed to serialize current_animation: {e}")
                            
                    if attr == "animations" and isinstance(val, (list, tuple)):
                        anims = []
                        for a in val:
                            try:
                                if isinstance(a, Resources.Resource) and a.resource_path:
                                    anims.append(a.resource_path)
                                    continue
                                
                                anims.append({
                                    "name": getattr(a, "name", None),
                                    "frame_size": getattr(a, "frame_size", None),
                                    "frames": getattr(a, "frames", None),
                                    "fps": getattr(a, "fps", None),
                                    "loop": getattr(a, "loop", None),
                                    "spritesheet_path": normalize_path(getattr(a, "spritesheet_path", None)),
                                })
                            except Exception as e:
                                SceneLoader._warn(f"Failed to serialize animation '{getattr(a, 'name', 'unknown')}': {e}")
                                continue

                        node_dict["properties"][attr] = anims

            for child in getattr(node, "_children", []):
                node_dict["children"].append(serialize_node(child))

            try:
                if hasattr(node, "texture"):
                     tex = getattr(node, "texture", None)
                     if isinstance(tex, Resources.Resource) and tex.resource_path:
                         node_dict["properties"]["texture"] = normalize_path(tex.resource_path)
                
                if hasattr(node, "audio"):
                     aud = getattr(node, "audio", None)
                     if isinstance(aud, Resources.Resource) and aud.resource_path:
                         node_dict["properties"]["audio"] = normalize_path(aud.resource_path)
                        
            except Exception as e:
                SceneLoader._warn(f"Failed to serialize specific resource properties: {e}")

            try:
                script_name = None
                if hasattr(node, "script") and isinstance(node.script, str):
                    script_name = node.script
                elif getattr(node, "runtime_script", None) is not None:
                    script_name = Resources.get_script_path(node.runtime_script)
                if script_name:
                    node_dict["properties"]["script"] = normalize_path(script_name)
            except Exception as e:
                SceneLoader._warn(f"Failed to serialize script: {e}")

            return node_dict

        scene_dict = {"name": getattr(scene, "name", None), "root": serialize_node(scene.root)}
        return scene_dict

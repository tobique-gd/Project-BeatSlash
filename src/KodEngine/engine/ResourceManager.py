import json
from . import (Nodes, NodeComponents, Scenes, Scripts)
from .ErrorHandler import ErrorHandler

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
            try:
                name = anim_meta.get("name")
                frame_size = tuple(anim_meta.get("frame_size"))
                frames = anim_meta.get("frames")
                fps = anim_meta.get("fps", 12)
                loop = anim_meta.get("loop", True)
                spritesheet_path = anim_meta.get("spritesheet_path")

                if spritesheet_path:
                    anim = NC.SpriteAnimation(name, spritesheet_path, frame_size, frames, loop, fps)
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
        # Set path on scene after successful save
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
            # Set path on scene after successful load
            if scene and hasattr(scene, 'path'):
                scene.path = file_path
            return scene
        except Exception as e:
            SceneLoader._error(f"Failed to deserialize scene from '{file_path}': {e}")
            return None
        
        
    @staticmethod
    def deserialize_scene(scene):
        if not isinstance(scene, dict) or "root" not in scene:
            return None

        def to_primitive(val):
            if isinstance(val, list):
                return tuple(val)
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
                    node.runtime_script = Scripts.load_script(script_name, node)
                except Exception as e:
                    SceneLoader._warn(f"Failed to load script '{script_name}': {e}")
            return node

        root_node = build_node(scene.get("root"))
        if Scenes.Scene is not None:
            return Scenes.Scene(scene.get("name"), root_node)
        return root_node

    @staticmethod
    def serialize_scene(scene):
        def is_primitive(v):
            return isinstance(v, (str, int, float, bool)) or v is None

        def serialize_value(v):
            if is_primitive(v):
                return v
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
                                anims.append({
                                    "name": getattr(a, "name", None),
                                    "frame_size": getattr(a, "frame_size", None),
                                    "frames": getattr(a, "frames", None),
                                    "fps": getattr(a, "fps", None),
                                    "loop": getattr(a, "loop", None),
                                    "spritesheet_path": getattr(a, "spritesheet_path", None),
                                })
                            except Exception as e:
                                SceneLoader._warn(f"Failed to serialize animation '{getattr(a, 'name', 'unknown')}': {e}")
                                continue

                        node_dict["properties"][attr] = anims

            for child in getattr(node, "_children", []):
                node_dict["children"].append(serialize_node(child))

            try:
                if hasattr(node, "texture_path") and isinstance(getattr(node, "texture_path"), str):
                    node_dict["properties"]["texture_path"] = getattr(node, "texture_path")
            except Exception as e:
                SceneLoader._warn(f"Failed to serialize texture_path: {e}")

            try:
                script_name = None
                if hasattr(node, "script") and isinstance(node.script, str):
                    script_name = node.script
                elif getattr(node, "runtime_script", None) is not None:
                    script_name = Scripts.get_script_path(node.runtime_script)
                if script_name:
                    node_dict["properties"]["script"] = script_name
            except Exception as e:
                SceneLoader._warn(f"Failed to serialize script: {e}")

            return node_dict

        scene_dict = {"name": getattr(scene, "name", None), "root": serialize_node(scene.root)}
        return scene_dict


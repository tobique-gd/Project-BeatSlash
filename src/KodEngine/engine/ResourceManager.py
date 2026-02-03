import json
from . import (Nodes, NodeComponents, Scenes)

class SceneLoader:
    def __init__(self) -> None:
        pass

    @staticmethod
    def save(file_path, save_data):
        data = SceneLoader.serialize_scene(save_data)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str, indent=2)
        
    
    @staticmethod
    def load(file_path):
        with open(file_path, "r") as f:
            data = json.load(f)
            return SceneLoader.deserialize_scene(data)
        
        
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
            except Exception:
                pass

            props = node_data.get("properties", {})
            current_animation_meta = None
            for k, v in props.items():
                if k == "current_animation":
                    current_animation_meta = v
                    continue
                value = to_primitive(v)
                try:
                    if k == "animations":
                        raise ValueError("Animations usage cannot be set directly from dict")
                    setattr(node, k, value)
                except Exception:
                    
                    if k == "audio_path" and hasattr(node, "audio"):
                        try:
                            node.audio = value
                        except Exception:
                            try:
                                setattr(node, "audio_path", value)
                            except Exception:
                                pass
                        
                    elif k == "texture_path" and hasattr(node, "texture"):
                        try:
                            
                            node.texture = value
                        except Exception:
                            try:
                                setattr(node, "texture_path", str(value))
            
                            except Exception:
                                pass
                    elif k == "animations":
                        try:
                            from . import NodeComponents as NC
                        except Exception:
                            NC = None

                        created = False
                        if NC is not None and isinstance(v, (list, tuple)) and hasattr(node, "add_animation"):
                            for anim_meta in v:
                                try:
                                    name = anim_meta.get("name")
                                    frame_size = tuple(anim_meta.get("frame_size"))
                                    frames = anim_meta.get("frames")
                                    fps = anim_meta.get("fps", 12)
                                    loop = anim_meta.get("loop", True)
                                    spritesheet_path = anim_meta.get("spritesheet_path")

        
                                    if spritesheet_path:
                                        try:
                                            import pygame
                                            try:
                                                surf = pygame.image.load(spritesheet_path).convert_alpha()
                                            except Exception:
                                                surf = None
                                        except Exception:
                                            surf = None

                                        try:
                                            if surf is not None:
                                                anim = NC.SpriteAnimation(name, surf, frame_size, frames, loop, fps)
                                            else:
                                                anim = NC.SpriteAnimation(name, spritesheet_path, frame_size, frames, loop, fps)
                                            try:
                                                node.add_animation(anim)
                                                
                                            except Exception:
                                                pass
                                            created = True
                                        except Exception:
                                            pass
                                except Exception:
                                    continue

                        if not created:
                            try:
                                setattr(node, "animations_meta", v)
                            except Exception:
                                pass
                    else:
                        pass
            
            if current_animation_meta and hasattr(node, "play"):
                try:
                    animation_name = current_animation_meta.get("name")
                    if animation_name:
                        node.play(animation_name)
                        
                        current_frame = current_animation_meta.get("current_frame")
                        if current_frame is not None and node.current_animation:
                            node.current_animation.current_frame = int(current_frame)
                except Exception as e:
                    print(f"Error restoring animation: {e}")

            for child_data in node_data.get("children", []):
                try:
                    child = build_node(child_data)
                    node.add_child(child)
                except Exception:
                    try:
                    
                        child = build_node(child_data)
                        child._parent = node
                        node._children.append(child)
                    except Exception:
                        pass

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
                if attr in ("_children", "_parent"):
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
                        except Exception:
                            pass
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
                            except Exception:
                                continue
                        node_dict["properties"][attr] = anims

            for child in getattr(node, "_children", []):
                node_dict["children"].append(serialize_node(child))

            try:
                if hasattr(node, "texture_path") and isinstance(getattr(node, "texture_path"), str):
                    node_dict["properties"]["texture_path"] = getattr(node, "texture_path")
            except Exception:
                pass

            return node_dict

        scene_dict = {"name": getattr(scene, "name", None), "root": serialize_node(scene.root)}
        return scene_dict


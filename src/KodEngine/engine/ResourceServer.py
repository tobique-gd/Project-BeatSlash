import json
import os
from . import (Nodes, Scenes, Resources)
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

        resource_cls = Resources.Resource.class_for_extension(ext)
        if resource_cls is None:
            return None

        try:
            res = resource_cls.from_path(path)
        except Exception as e:
            ErrorHandler.throw_warning(f"Failed to load resource '{path}': {e}")
            return None

        ResourceLoader._cache[path] = res
        return res

#SceneLoader handles saving and loading scenes
# its structured as staticmethods to allow for clean calling of the load and save functions 
class SceneLoader:
    RESOURCE_KEY = "__resource__"

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

    @staticmethod
    def _normalize_resource_payload(data: dict):
        normalized = {}
        for key, value in data.items():
            if isinstance(value, str) and (key == "resource_path" or key.endswith("_path")):
                normalized[key] = SceneLoader._to_project_relative(value)
            elif isinstance(value, tuple):
                normalized[key] = list(value)
            else:
                normalized[key] = value
        return normalized

    @staticmethod
    def _resolve_resource_payload(data: dict):
        resolved = {}
        for key, value in data.items():
            if isinstance(value, str) and (key == "resource_path" or key.endswith("_path")):
                resolved[key] = ResourceLoader.resolve_path(value)
            else:
                resolved[key] = value
        return resolved

    @staticmethod
    def _encode_value(value):
        if isinstance(value, Resources.Resource):
            encoded_resource = SceneLoader._encode_value(value.to_dict())
            return {SceneLoader.RESOURCE_KEY: encoded_resource}

        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, str):
                return SceneLoader._to_project_relative(value)
            return value

        if isinstance(value, (list, tuple)):
            out = []
            for item in value:
                encoded = SceneLoader._encode_value(item)
                if encoded is None and item is not None:
                    return None
                out.append(encoded)
            return out

        if isinstance(value, dict):
            out = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    return None
                encoded = SceneLoader._encode_value(item)
                if encoded is None and item is not None:
                    return None
                out[key] = encoded
            return out

        return None

    @staticmethod
    def _decode_sequence(values):
        decoded = [SceneLoader._decode_value(v) for v in values]
        if all(isinstance(item, (str, int, float, bool)) or item is None for item in decoded):
            return tuple(decoded)
        return decoded

    @staticmethod
    def _decode_value(value):
        if isinstance(value, dict):
            if SceneLoader.RESOURCE_KEY in value:
                payload = value.get(SceneLoader.RESOURCE_KEY)
                if isinstance(payload, dict):
                    payload = SceneLoader._resolve_resource_payload(payload)
                    decoded_payload = {k: SceneLoader._decode_value(v) for k, v in payload.items()}

                    resource_path = decoded_payload.get("resource_path")
                    if isinstance(resource_path, str):
                        loaded = ResourceLoader.load(resource_path)
                        if isinstance(loaded, Resources.Resource):
                            return loaded

                    try:
                        resource = Resources.Resource.from_dict(decoded_payload)
                        if resource is not None:
                            return resource
                    except Exception:
                        return value
                return value
            
            return {k: SceneLoader._decode_value(v) for k, v in value.items()}

        if isinstance(value, list):
            return SceneLoader._decode_sequence(value)

        return value

    #reading scene files (.kscn) that are basically json
    @staticmethod
    def _json_pretty_with_compact_tile_rows(value, indent=2, level=0, parent_key=None):
        pad = " " * (indent * level)
        child_pad = " " * (indent * (level + 1))

        if isinstance(value, dict):
            if not value:
                return "{}"

            lines = ["{"]
            items = list(value.items())
            for index, (key, item) in enumerate(items):
                key_text = json.dumps(str(key), ensure_ascii=False)
                item_text = SceneLoader._json_pretty_with_compact_tile_rows(
                    item,
                    indent=indent,
                    level=level + 1,
                    parent_key=str(key),
                )
                comma = "," if index < len(items) - 1 else ""
                lines.append(f"{child_pad}{key_text}: {item_text}{comma}")

            lines.append(f"{pad}}}")
            return "\n".join(lines)

        if isinstance(value, list):
            if not value:
                return "[]"

            if parent_key in {"tile_data", "_tile_data"} and all(
                isinstance(row, (list, tuple)) and all(isinstance(cell, (int, float, str, bool)) or cell is None for cell in row)
                for row in value
            ):
                lines = ["["]
                for index, row in enumerate(value):
                    row_text = json.dumps(list(row), ensure_ascii=False, separators=(", ", ": "))
                    comma = "," if index < len(value) - 1 else ""
                    lines.append(f"{child_pad}{row_text}{comma}")
                lines.append(f"{pad}]")
                return "\n".join(lines)

            lines = ["["]
            for index, item in enumerate(value):
                item_text = SceneLoader._json_pretty_with_compact_tile_rows(
                    item,
                    indent=indent,
                    level=level + 1,
                    parent_key=None,
                )
                comma = "," if index < len(value) - 1 else ""
                lines.append(f"{child_pad}{item_text}{comma}")
            lines.append(f"{pad}]")
            return "\n".join(lines)

        return json.dumps(value, ensure_ascii=False)

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
            serialized = SceneLoader._json_pretty_with_compact_tile_rows(data, indent=2)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(serialized)
                f.write("\n")
            return True
        except Exception as e:
            SceneLoader._error(f"Failed to write scene to '{file_path}': {e}")
            return False

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

        def build_node(node_data):
            tname = node_data.get("type")
            cls = getattr(Nodes, tname, getattr(Nodes, "Node", None))
            if cls is None:
                raise RuntimeError(f"Unknown node class: {tname}")

            node = cls()
            
            # Name handling (kept explicit as it's often special)
            if "name" in node_data:
                node.name = node_data["name"]

            # Load properties via data-oriented method
            props = node_data.get("properties", {})
            try:
                decoded_props = SceneLoader._decode_value(props)
                if isinstance(decoded_props, dict):
                     node.load_data(decoded_props)
            except Exception as e:
                SceneLoader._warn(f"Failed to load data for node '{node.name}': {e}")
            
            # Recurse children
            for child_data in node_data.get("children", []):
                try:
                    child = build_node(child_data)
                    node.add_child(child)
                except Exception as e:
                    SceneLoader._warn(f"Failed to add child: {e}")
            
            return node

        root_node = build_node(scene.get("root"))
        if Scenes.Scene is not None:
            return Scenes.Scene(scene.get("name"), root_node)
        return root_node

    @staticmethod
    def serialize_scene(scene):
        def serialize_node(node):
            node_dict = {
                "type": type(node).__name__,
                "name": node.name,
                "properties": {},
                "children": []
            }

            try:
                 # Data-oriented saving: Resource says how it is saved
                 raw_data = node.save_data()
                 encoded_data = SceneLoader._encode_value(raw_data)
                 if isinstance(encoded_data, dict):
                     node_dict["properties"] = encoded_data
            except Exception as e:
                SceneLoader._warn(f"Failed to save data for node '{node.name}': {e}")

            for child in getattr(node, "_children", []):
                node_dict["children"].append(serialize_node(child))

            return node_dict

        scene_dict = {"name": getattr(scene, "name", None), "root": serialize_node(scene.root)}
        return scene_dict

import json
import os
from enum import Enum
from . import (Nodes, Scenes, Resources)
from .ErrorHandler import ErrorHandler

#ResourceLoader handles caching, loading and saving resources liek audio, textures
#might need to redo this to be extendable easily and i wont have to manually define acceptable formats its just a little hacky
class ResourceLoader:
    """Load, resolve, and cache resource files for the engine."""

    _cache = {}
    _project_root = None

    @staticmethod
    def set_project_root(path: str):
        """Set the root directory used to resolve project-relative paths.

        Parameters
        ----------
        path:
            Absolute or relative path to the project root.
        """
        ResourceLoader._project_root = os.path.abspath(path)

    @staticmethod
    def resolve_path(path: str):
        """Resolve a possibly project-relative path to an absolute path.

        Parameters
        ----------
        path:
            Path to resolve.

        Returns
        -------
        str
            Absolute path when the file can be resolved, otherwise the input
            path unchanged.
        """
        if not os.path.isabs(path) and ResourceLoader._project_root:
             potential_path = os.path.join(ResourceLoader._project_root, path)
             if os.path.exists(potential_path):
                 return potential_path
        return path

    @staticmethod
    def load(path: str):
        """Load a resource from disk and cache the loaded instance.

        Parameters
        ----------
        path:
            Path to the resource file.

        Returns
        -------
        object | None
            Loaded resource instance, or ``None`` when the file cannot be
            resolved or decoded.
        """
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
    """Serialize and deserialize scene trees to the on-disk JSON format."""

    RESOURCE_KEY = "__resource__"

    def __init__(self) -> None:
        """Create a scene loader instance."""
        pass

    @staticmethod
    def _warn(message: str):
        """Send a warning through the engine error handler."""
        ErrorHandler.throw_warning(message)

    @staticmethod
    def _error(message: str):
        """Send an error through the engine error handler."""
        ErrorHandler.throw_error(message)

    @staticmethod
    def _to_project_relative(path: str):
        """Convert an absolute path into a project-relative path when possible."""
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
        """Normalize a resource payload before serialization.

        Parameters
        ----------
        data:
            Resource dictionary to normalize.

        Returns
        -------
        dict
            Normalized dictionary with project-relative paths and JSON-safe
            sequence values.
        """
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
        """Resolve project-relative paths in a decoded resource payload."""
        resolved = {}
        for key, value in data.items():
            if isinstance(value, str) and (key == "resource_path" or key.endswith("_path")):
                resolved[key] = ResourceLoader.resolve_path(value)
            else:
                resolved[key] = value
        return resolved

    @staticmethod
    def _encode_value(value):
        """Encode a scene value into JSON-safe data.

        Parameters
        ----------
        value:
            Value to encode.

        Returns
        -------
        object | None
            JSON-serializable value, or ``None`` when the value cannot be
            represented safely.
        """
        if isinstance(value, Enum):
            return value.value

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
        """Decode a JSON sequence back into engine data types."""
        decoded = [SceneLoader._decode_value(v) for v in values]
        if all(isinstance(item, (str, int, float, bool)) or item is None for item in decoded):
            return tuple(decoded)
        return decoded

    @staticmethod
    def _decode_value(value):
        """Decode a JSON value back into engine data types."""
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
    import json

    @staticmethod
    def _json_pretty_with_compact_tile_rows(value):
        """Serialize scene data to indented JSON text."""
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), indent=4)

    @staticmethod
    def _read_json(file_path):
        """Read JSON from disk and report loader errors through the engine."""
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
        """Write scene JSON to disk.

        Returns
        -------
        bool
            ``True`` when the write succeeds, otherwise ``False``.
        """
        try:
            serialized = SceneLoader._json_pretty_with_compact_tile_rows(data)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(serialized)
                f.write("\n")
            return True
        except Exception as e:
            SceneLoader._error(f"Failed to write scene to '{file_path}': {e}")
            return False

    @staticmethod
    def save(save_data, file_path):
        """Serialize a scene object and write it to disk.

        Parameters
        ----------
        save_data:
            Scene-like object with a ``root`` attribute.
        file_path:
            Output file path.

        Returns
        -------
        bool
            ``True`` when saving succeeds, otherwise ``False``.
        """
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
        """Load a scene from a JSON file.

        Parameters
        ----------
        file_path:
            Scene file to load.

        Returns
        -------
        Scene | Node | None
            Loaded scene object, root node, or ``None`` on failure.
        """
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
    def deserialize_node(node_data):
            """Rebuild a node tree from serialized node data."""
            props = node_data.get("properties", {})
            

            try:
                decoded_props = SceneLoader._decode_value(props)
            except Exception as e:
                decoded_props = {}
                SceneLoader._warn(f"Failed to decode properties for '{node_data.get('name', 'Unknown')}': {e}")

            is_linked = isinstance(decoded_props, dict) and decoded_props.get("is_linked_scene", False)

            if is_linked:
                linked_path = decoded_props.get("linked_scene_path")
                if not linked_path:
                    raise RuntimeError(f"Linked scene '{node_data.get('name')}' is missing 'linked_scene_path'.")
                
                resolved_path = ResourceLoader.resolve_path(linked_path)
                linked_scene = SceneLoader.load(resolved_path)
                
                if not linked_scene or not linked_scene.root:
                    raise RuntimeError(f"Failed to load linked scene from '{resolved_path}'.")
                
                node = linked_scene.root
                
                node.is_linked_scene = True
                node.linked_scene_path = linked_path
            else:
                tname = node_data.get("type")
                cls = getattr(Nodes, tname, getattr(Nodes, "Node", None))
                if cls is None:
                    raise RuntimeError(f"Unknown node class: {tname}")
                node = cls()

            if "name" in node_data:
                node.name = node_data["name"]

            
            if isinstance(decoded_props, dict):
                try:
                    node.load_data(decoded_props)
                except Exception as e:
                    SceneLoader._warn(f"Failed to load data for node '{node.name}': {e}")

            if not is_linked:
                for child_data in node_data.get("children", []):
                    try:
                        child = SceneLoader.deserialize_node(child_data)
                        if child:
                            node.add_child(child)
                    except Exception as e:
                        SceneLoader._warn(f"Failed to add child: {e}")
                        
            return node

    @staticmethod
    def deserialize_scene(scene):
        """Rebuild a scene object from serialized scene data."""
        if not isinstance(scene, dict) or "root" not in scene:
            return None

        

        try:
            root_node = SceneLoader.deserialize_node(scene.get("root"))
            if Scenes.Scene is not None:
                return Scenes.Scene(scene.get("name"), root_node)
            return root_node
        except Exception as e:
            SceneLoader._error(f"Error building scene tree: {e}")
            return None

    @staticmethod
    def serialize_node(node):
        """Convert a node tree into a serializable dictionary."""
        node_dict = {
            "type": type(node).__name__,
            "name": node.name,
            "properties": {},
            "children": []
        }

        try:
                raw_data = node.save_data()
                encoded_data = SceneLoader._encode_value(raw_data)
                if isinstance(encoded_data, dict):
                    node_dict["properties"] = encoded_data
        except Exception as e:
            SceneLoader._warn(f"Failed to save data for node '{node.name}': {e}")

        if getattr(node, "is_linked_scene", False):
            node_dict["properties"]["is_linked_scene"] = True
            node_dict["properties"]["linked_scene_path"] = SceneLoader._to_project_relative(node.linked_scene_path)
            return node_dict

        for child in getattr(node, "_children", []):
            node_dict["children"].append(SceneLoader.serialize_node(child))

        return node_dict

    @staticmethod
    def serialize_scene(scene):
        """Convert a scene object into a serializable dictionary."""
        

        scene_dict = {"name": getattr(scene, "name", None), "root": SceneLoader.serialize_node(scene.root)}
        return scene_dict

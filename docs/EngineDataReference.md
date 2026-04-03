# Engine Nodes and Resources Reference

## Node Model

All scene objects derive from Node in src/KodEngine/engine/Nodes.py. Node manages parent and child links, lookup by path, recursive type queries, script binding, and serialization hooks. Node2D adds transform fields and world position propagation.

## Scene Serialization

SceneLoader in src/KodEngine/engine/ResourceServer.py reads and writes .kscn files as JSON payloads. Node type names are stored as class names. Node fields are serialized through save_data and restored through load_data. Resource instances are encoded with marker payloads. Linked scenes are restored through is_linked_scene and linked_scene_path.

## Resource Loading

ResourceLoader resolves project-relative paths against the configured project root. It caches loaded resources by absolute path and instantiates resource classes through extension lookup. The type and extension registries are defined by Resource subclasses in src/KodEngine/engine/Resources.py.

## Built-In Resources

Built-in resource classes include Texture2D, AudioStream, Script, SpriteAnimation, Tileset2D, Tile2D, CollisionShape, and CollisionRectangleShape. Resource objects support path-based loading, dictionary serialization, and nested resource encoding.

## Scripting Model

Node script slots are stored as Script resources and resolved at runtime through load_script. Runtime calls _ready, _process(delta), and _input(event) when handlers are present. If a module defines SCRIPT_CLASS or __script_class__, runtime instantiates that class with the node binding. Otherwise runtime uses ScriptProxy with module-level handlers.

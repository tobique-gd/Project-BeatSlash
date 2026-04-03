# Node

Node is the base class for all scene graph objects.

| Function | Description |
| --- | --- |
| __init__() | Initializes core fields, parent links, script state, and linked scene flags. |
| _on_enter() | Recursively calls child enter handlers. |
| on_exit() | Recursively calls child exit handlers. |
| add_child(_node) | Appends a child and sets parent reference. |
| remove_child(_node) | Removes a child and clears parent reference. |
| queue_free() | Marks the node for deferred deletion. |
| clone() | Serializes and deserializes the node to create a copy. |
| get_node(_path_to_child) | Resolves a child node by slash path. |
| get_child(index) | Returns child at index or None. |
| get_nodes_by_type(node_type) | Recursively collects children by type. |
| set_script(module_name) | Assigns a script resource path. |
| reparent_to(new_parent) | Moves the node to a new parent. |
| script (property getter) | Returns current script resource. |
| script (property setter) | Accepts resource, path, or None and binds runtime script. |
| _update(_delta) | Per-frame runtime hook for subclasses. |
| editor_update(delta) | Per-frame editor hook for subclasses. |
| save_data() | Serializes public non-callable fields. |
| load_data(data) | Loads serialized fields into node properties. |

| Property | Description |
| --- | --- |
| name | Node name, defaults to the class name. |
| script | Bound script resource or resource path. |
| runtime_script | Loaded runtime script instance, if a script is assigned. |
| is_linked_scene | Marks the node as originating from a linked scene. |
| linked_scene_path | Path to the linked scene resource. |

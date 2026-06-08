import os
import random
from KodEngine.engine import ResourceServer


MAP_TILES_DIR = "scenes/map_tiles"
MIN_ROOM_COUNT = 4


def _collect_tile_scene_paths():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tiles_dir = os.path.abspath(os.path.join(script_dir, "..", MAP_TILES_DIR))
    if not os.path.isdir(tiles_dir):
        return []
    paths = []
    for filename in sorted(os.listdir(tiles_dir)):
        if not filename.endswith(".kscn"):
            continue
        if filename in {"tile_right_01.kscn", "dungeon_root.kscn"}:
            continue
        paths.append(os.path.join(MAP_TILES_DIR, filename))
    return paths


def _find_player_node(node):
    if node is None:
        return None
    if getattr(node, "name", None) == "Player":
        return node
    for child in getattr(node, "_children", []):
        found = _find_player_node(child)
        if found is not None:
            return found
    return None


def _resolve_player_root(node):
    current = node
    while current is not None:
        if getattr(current, "name", None) == "Player":
            return current
        current = getattr(current, "_parent", None)
    return None


def _room_connector_names(room):
    names = []
    connectors = room.get_node("connectors")
    if connectors is None:
        return names
    for connector_name in ("connector_left", "connector_right", "connector_up", "connector_down"):
        if connectors.get_node(connector_name) is not None:
            names.append(connector_name)
    return names


def _find_connector(room, connector_name):
    return room.get_node(f"connectors/{connector_name}")


def _opposite_connector_name(connector_name):
    return {
        "connector_left": "connector_right",
        "connector_right": "connector_left",
        "connector_up": "connector_down",
        "connector_down": "connector_up",
    }.get(connector_name, connector_name)


def _make_room_name(self, base_name):
    self._room_counter += 1
    return f"{base_name}_{self._room_counter}"


def _load_room_template(self, scene_path):
    scene = self.node.preload(scene_path)
    if scene is None:
        return None
    room = self.node.instantiate(scene)
    return room


def _register_room(self, room):
    if room is None:
        return room
    for existing in self._rooms:
        if existing is room:
            return room
    self._rooms.append(room)
    return room


def _attach_room_nodes(self, room):
    tilemap = room.get_node("TileMap2D")
    root_tilemaps = self.node.get_node("Tilemaps")
    if tilemap is not None and root_tilemaps is not None:
        world_pos = tilemap.global_position
        root_tilemaps.add_child(tilemap)
        tilemap.global_position = world_pos
        tilemap._source_room = room

    room_ysort = room.get_node("YSort2D")
    root_ysort = self.node.get_node("YSort2D")
    if room_ysort is not None and root_ysort is not None:
        children = list(getattr(room_ysort, "_children", []))
        for child in children:
            world_pos = child.global_position
            root_ysort.add_child(child)
            child.global_position = world_pos
            child._source_room = room

    room_coll = room.get_node("StaticBody2D")
    root_coll = self.node.get_node("Collisions")
    if room_coll is not None and root_coll is not None:
        world_pos = room_coll.global_position
        root_coll.add_child(room_coll)
        room_coll.global_position = world_pos
        room_coll._source_room = room


MUSIC_DIR = "assets/audio"

def _load_music(self):
    self._songs = []
    music_dir_abs = ResourceServer.ResourceLoader.resolve_path(MUSIC_DIR)
    if not os.path.isdir(music_dir_abs):
        print(f"Music directory not found: {music_dir_abs}")
        return
    for filename in sorted(os.listdir(music_dir_abs)):
        if not filename.endswith(".mp3"):
            continue
        relative_path = os.path.join(MUSIC_DIR, filename)
        try:
            resource = ResourceServer.ResourceLoader.load(relative_path)
            if resource is not None:
                self._songs.append(resource)
        except Exception:
            pass


def _pick_music(self):
    print((self._songs))
    if self._audio_player is None or not self._songs:
        return
    track = random.choice(self._songs)
    self._audio_player.audio = track
    self._audio_player.play()


def _ready(self):
    self._rooms = []
    self._room_counter = 0
    self._tile_scene_paths = _collect_tile_scene_paths()
    self._current_room = None
    self._player = None
    self._next_room_key = 0
    self._room_key = {}
    self._room_bounds_cache = {}
    self._node_data = {}
    self._key_by_node = {}
    self._songs = []

    self._audio_player = self.node.get_node("AudioPlayer")
    if self._audio_player is not None:
        self._audio_player.connect("finished", target=self, method="_on_audio_finished")

    _load_music(self)
    _pick_music(self)

    start_room = _load_room_template(self, os.path.join(MAP_TILES_DIR, "tile_right_01.kscn"))
    if start_room is None:
        return

    self._player = _find_player_node(start_room)

    start_key = _assign_room_key(self, start_room)
    _record_node_data(self, start_key, start_room,
                      os.path.join(MAP_TILES_DIR, "tile_right_01.kscn"),
                      getattr(start_room, "global_position", (0.0, 0.0)))
    _register_room(self, start_room)
    _attach_room_nodes(self, start_room)
    _cache_room_bounds(self, start_room)
    _set_current_room(self, start_room, self._player)
    _build_initial_chain(self, start_room, MIN_ROOM_COUNT - 1)


def _on_audio_finished(self):
    _pick_music(self)


def _assign_room_key(self, room):
    key = self._next_room_key
    self._next_room_key += 1
    self._room_key[id(room)] = key
    self._key_by_node[room] = key
    return key


def _get_room_key(self, room):
    return self._key_by_node.get(room)


def _record_node_data(self, key, room, scene_path, world_pos):
    if key not in self._node_data:
        self._node_data[key] = {
            "scene_path": scene_path,
            "world_pos": world_pos,
            "edges": {},
            "live_room": room,
        }
    else:
        self._node_data[key]["live_room"] = room
        self._node_data[key]["world_pos"] = world_pos


def _link_rooms(self, src_key, src_connector, dst_key, dst_connector):
    self._node_data[src_key]["edges"][src_connector] = dst_key
    self._node_data[dst_key]["edges"][dst_connector] = src_key


def _find_attachment_connector(room, preferred_name):
    connector = _find_connector(room, preferred_name)
    if connector is not None:
        return connector
    for connector_name in _room_connector_names(room):
        if connector_name == preferred_name:
            continue
        connector = _find_connector(room, connector_name)
        if connector is not None:
            return connector
    return None


def _spawn_connected_room(self, source_room, source_connector_name):
    source_connector = _find_connector(source_room, source_connector_name)
    if source_connector is None:
        return None

    preferred_connector_name = _opposite_connector_name(source_connector_name)
    candidate_paths = list(self._tile_scene_paths)
    random.shuffle(candidate_paths)

    for scene_path in candidate_paths:
        room = _load_room_template(self, scene_path)
        if room is None:
            continue

        attachment_connector = _find_connector(room, preferred_connector_name)
        if attachment_connector is None:
            continue

        room.name = _make_room_name(self, room.name)
        room.global_position = (0.0, 0.0)

        connector_offset_x = float(attachment_connector.global_position[0])
        connector_offset_y = float(attachment_connector.global_position[1])
        room.global_position = (
            float(source_connector.global_position[0]) - connector_offset_x,
            float(source_connector.global_position[1]) - connector_offset_y,
        )

        world_pos = room.global_position
        room_key = _assign_room_key(self, room)
        _record_node_data(self, room_key, room, scene_path, world_pos)

        src_key = _get_room_key(self, source_room)
        if src_key is not None:
            _link_rooms(self, src_key, source_connector_name, room_key, preferred_connector_name)

        if not hasattr(source_room, "_spawned_connectors"):
            source_room._spawned_connectors = set()
        source_room._spawned_connectors.add(source_connector_name)

        if not hasattr(room, "_spawned_connectors"):
            room._spawned_connectors = set()
        room._spawned_connectors.add(preferred_connector_name)

        _register_room(self, room)
        _attach_room_nodes(self, room)
        _cache_room_bounds(self, room)

        random.shuffle(self._tile_scene_paths)
        return room

    return None


def _reload_room_at(self, key):
    data = self._node_data.get(key)
    if data is None:
        return None

    if data["live_room"] is not None:
        return data["live_room"]

    scene_path = data["scene_path"]
    world_pos = data["world_pos"]

    room = _load_room_template(self, scene_path)
    if room is None:
        return None

    room.name = _make_room_name(self, room.name)
    room.global_position = world_pos

    self._key_by_node[room] = key
    data["live_room"] = room

    room._spawned_connectors = set(data["edges"].keys())

    _register_room(self, room)
    _attach_room_nodes(self, room)
    _cache_room_bounds(self, room)

    return room


def _ensure_neighbours_loaded(self, room):
    key = _get_room_key(self, room)
    if key is None:
        return

    data = self._node_data.get(key, {})
    edges = data.get("edges", {})
    for connector_name, neighbour_key in edges.items():
        neighbour_data = self._node_data.get(neighbour_key)
        if neighbour_data is None:
            continue
        if neighbour_data["live_room"] is None:
            _reload_room_at(self, neighbour_key)


def _expand_from_room(self, room):
    _ensure_neighbours_loaded(self, room)

    spawned_connectors = getattr(room, "_spawned_connectors", set())
    unspawned = [c for c in _room_connector_names(room) if c not in spawned_connectors]
    if unspawned:
        for connector_name in unspawned:
            _spawn_connected_room(self, room, connector_name)


def _build_initial_chain(self, start_room, depth):
    current_room = start_room
    came_from_connector = None

    for step in range(max(0, depth)):
        next_room = None

        available_connectors = [
            name for name in _room_connector_names(current_room)
            if name not in getattr(current_room, "_spawned_connectors", set())
            and name != came_from_connector
        ]

        for connector_name in available_connectors:
            next_room = _spawn_connected_room(self, current_room, connector_name)
            if next_room is not None:
                came_from_connector = _opposite_connector_name(connector_name)
                break

        if next_room is None:
            break
        current_room = next_room


def _cache_room_bounds(self, room):
    key = _get_room_key(self, room)
    if key is None:
        return
    tilemap = _get_room_tilemap(self, room)
    if tilemap is None:
        return
    try:
        bounds = tilemap.world_bounds
        if bounds is None:
            return
        (lx, ly), (hx, hy) = bounds
        tx = float(tilemap.global_position[0])
        ty = float(tilemap.global_position[1])
        world_bounds = ((lx + tx, ly + ty), (hx + tx, hy + ty))
        self._room_bounds_cache[key] = world_bounds
    except Exception:
        pass


from collections import deque


def _collect_rooms_within_distance(self, start_key, max_distance=2):
    if start_key is None:
        return set()
    visited = {start_key}
    queue = deque([(start_key, 0)])
    while queue:
        key, distance = queue.popleft()
        if distance >= max_distance:
            continue
        node_data = self._node_data.get(key)
        if node_data is None:
            continue
        for neighbour_key in node_data.get("edges", {}).values():
            if neighbour_key not in visited:
                visited.add(neighbour_key)
                queue.append((neighbour_key, distance + 1))
    return visited


def _get_room_bounds(self, room):
    key = _get_room_key(self, room)
    tilemap = _get_room_tilemap(self, room)
    if tilemap is not None:
        try:
            bounds = tilemap.world_bounds
            if bounds is not None and key is not None:
                (lx, ly), (hx, hy) = bounds
                tx = float(tilemap.global_position[0])
                ty = float(tilemap.global_position[1])
                world_bounds = ((lx + tx, ly + ty), (hx + tx, hy + ty))
                self._room_bounds_cache[key] = world_bounds
                return world_bounds
        except Exception:
            pass
    if key is not None:
        return self._room_bounds_cache.get(key)
    return None


def _room_camera_limits(self, room):
    bounds = _get_room_bounds(self, room)
    if bounds is None:
        return (-1, -1), (-1, -1)

    (min_world_x, min_world_y), (max_world_x, max_world_y) = bounds

    has_left  = _find_connector(room, "connector_left")  is not None
    has_right = _find_connector(room, "connector_right") is not None
    has_up    = _find_connector(room, "connector_up")    is not None
    has_down  = _find_connector(room, "connector_down")  is not None

    limit_min = (
        min_world_x if not has_left  else -1,
        -1,
    )
    limit_max = (
        max_world_x if not has_right else -1,
        -1,
    )
    return limit_min, limit_max


def _detect_current_room(self):
    if self._player is None:
        return None
    player_pos = getattr(self._player, "global_position", None)
    if player_pos is None:
        return None
    px, py = float(player_pos[0]), float(player_pos[1])
    for room in self._rooms:
        bounds = _get_room_bounds(self, room)
        if bounds is None:
            continue
        (min_x, min_y), (max_x, max_y) = bounds
        if min_x <= px <= max_x and min_y <= py <= max_y:
            return room
    return None


def _process(self, delta):
    detected_room = _detect_current_room(self)
    room_changed = detected_room is not None and detected_room is not self._current_room
    if room_changed:
        _set_current_room(self, detected_room, self._player)
        _expand_from_room(self, self._current_room)
        _prune_far_rooms(self, self._current_room)


def _set_player_room(self, room, player):
    if room is None or player is None:
        return
    root_ysort = self.node.get_node("YSort2D")
    if root_ysort is None:
        return

    world_position = getattr(player, "global_position", (0, 0))
    if getattr(player, "_parent", None) is not root_ysort:
        player.reparent_to(root_ysort)
        player.global_position = world_position
    player._source_room = None

    camera = player.get_node("Camera2D")
    if camera is not None:
        camera.current = True
        limit_min, limit_max = _room_camera_limits(self, room)
        camera.limit_min = limit_min
        camera.limit_max = limit_max


def _set_current_room(self, room, player=None):
    self._current_room = room
    _set_player_room(self, room, player)


def _get_room_tilemap(self, room):
    root_tilemaps = self.node.get_node("Tilemaps")
    if root_tilemaps is None:
        return None
    for child in getattr(root_tilemaps, "_children", []):
        if getattr(child, "_source_room", None) is room:
            return child
    return None


def _room_world_bounds(self, room):
    return _get_room_bounds(self, room)


from KodEngine.engine import Globals


def _is_room_off_screen(self, room, camera, margin=2048):
    key = _get_room_key(self, room)
    bounds = _get_room_bounds(self, room)
    if bounds is None:
        return False

    (min_x, min_y), (max_x, max_y) = bounds
    app = getattr(Globals, "APP", None)
    if app is None:
        return False

    zoom = getattr(camera, "zoom", 1.0)
    if isinstance(zoom, (list, tuple)):
        zoom = zoom[0] if zoom else 1.0
    try:
        zoom = max(0.05, float(zoom))
    except Exception:
        zoom = 1.0

    viewport_size = getattr(
        app,
        "internal_resolution",
        app.configuration.project_settings["window"]["internal_viewport_resolution"],
    )
    cam_x, cam_y = app.renderer._get_camera_world_position_for_viewport(
        camera, viewport_size, zoom
    )
    viewport_w = viewport_size[0] / zoom
    viewport_h = viewport_size[1] / zoom
    half_w = viewport_w * 0.5 + margin
    half_h = viewport_h * 0.5 + margin

    screen_min_x = cam_x - half_w
    screen_max_x = cam_x + half_w
    screen_min_y = cam_y - half_h
    screen_max_y = cam_y + half_h

    return (
        max_x < screen_min_x
        or min_x > screen_max_x
        or max_y < screen_min_y
        or min_y > screen_max_y
    )


def _free_room_nodes(self, room):
    key = _get_room_key(self, room)

    root_tilemaps = self.node.get_node("Tilemaps")
    root_ysort    = self.node.get_node("YSort2D")
    root_coll     = self.node.get_node("Collisions")

    if root_tilemaps is not None:
        for child in list(getattr(root_tilemaps, "_children", [])):
            if getattr(child, "_source_room", None) is room:
                root_tilemaps.remove_child(child)
                child.queue_free()

    if root_ysort is not None:
        for child in list(getattr(root_ysort, "_children", [])):
            if child is self._player:
                continue
            if getattr(child, "_source_room", None) is room:
                root_ysort.remove_child(child)
                child.queue_free()

    if root_coll is not None:
        for child in list(getattr(root_coll, "_children", [])):
            if getattr(child, "_source_room", None) is room:
                root_coll.remove_child(child)
                child.queue_free()

    if key is not None and key in self._node_data:
        self._node_data[key]["live_room"] = None

    self._key_by_node.pop(room, None)
    self._rooms = [r for r in self._rooms if r is not room]

    room.queue_free()


def _prune_far_rooms(self, current_room):
    current_key = _get_room_key(self, current_room)
    if current_key is None:
        return

    keep_keys = _collect_rooms_within_distance(self, current_key, max_distance=1)

    for room in list(self._rooms):
        if room is current_room:
            continue
        room_key = _get_room_key(self, room)
        if room_key is None or room_key not in keep_keys:
            _free_room_nodes(self, room)
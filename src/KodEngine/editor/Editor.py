# GENERAL IMPORTS
import json
import os
import sys
import platform
import subprocess
import copy
import warnings
from collections import deque
import traceback

import dearpygui.dearpygui as pygui
import numpy as np

warnings.filterwarnings(
    "ignore",
    message=r"pkg_resources is deprecated as an API.*",
    category=UserWarning,
    module=r"pygame\.pkgdata",
)

import pygame

# Run in dummy mode to avoid DPG/Pygame event overlap in the editor process.
os.environ["SDL_VIDEODRIVER"] = "dummy"

from . import DebugRenderingServer
from .EditorGizmo import EditorGizmoController
from .EditorModels import EditorCommand, EditorCommandType, EditorMode
from .EditorTools import EditorViewportToolController
from .EditorOverlay import EditorOverlayRenderer
from .EditorUI import EditorUI
from ..engine import Kod, Nodes, ResourceServer
from ..engine.ErrorHandler import ErrorHandler


def debug(msg):
    print(f"[KodEditor] {msg}")
    sys.stdout.flush()


def _merge_settings_dict(target, override):
    if not isinstance(target, dict) or not isinstance(override, dict):
        return target

    for key, value in override.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            _merge_settings_dict(current, value)
            continue
        target[key] = value

    return target

class EditorSettings:
    def __init__(self):
        self.editor_settings = {
            "debug" : {
                "editor_resolution": (1920, 1080),
                "default_background_color": (50, 50, 50),
                "default_gizmo_color": (255, 165, 0),
                "default_camera_gizmo_color": (181, 102, 237),
                "default_collision_color": (0, 162, 255),
                "default_x_axis_color": (255, 0, 0),
                "default_y_axis_color": (0, 255, 0),
            },
            "file_management" : {
                "file_extension_commands" : {
                    ".kscn" : "--editor",
                    ".py" : "--default",
                    ".png" : "--default",
                    ".jpg" : "--default",
                    ".jpeg" : "--default",
                    ".bmp" : "--default",
                    ".tga" : "--default",
                    ".gif" : "--default",
                    ".wav" : "--default",
                    ".ogg" : "--default",
                    ".mp3" : "--default"

                }
            },
            "keyboard_shortcuts" : {
                "save_scene": {"modifiers": ["ctrl"], "key": "s"},
                "load_scene": {"modifiers": ["ctrl"], "key": "o"},
                "run_scene": {"modifiers": ["ctrl"], "key": "r"},
                "run_project": {"modifiers": ["ctrl", "shift"], "key": "r"},
                "open_editor_settings": {"modifiers": ["ctrl"], "key": ","},
                "duplicate_node": {"modifiers": ["ctrl"], "key": "d"},
                "copy_node": {"modifiers": ["ctrl"], "key": "c"},
                "paste_node": {"modifiers": ["ctrl"], "key": "v"}
            }
        }




class KodEditor:
    def __init__(self):
        ErrorHandler.set_editor_mode(True)
        self.settings = Kod.Settings()
        self.editor_settings = EditorSettings()

        self._project_directory = self._discover_project_directory()
        self._load_persistent_settings()

        runtime_window_settings = self.settings.project_settings.get("window", {})
        self.runtime_window_settings = {
            "viewport_resolution": tuple(runtime_window_settings.get("viewport_resolution", (640, 360))),
            "internal_viewport_resolution": tuple(runtime_window_settings.get("internal_viewport_resolution", (640, 360))),
        }

        project_dir = self.settings.project_settings["file_management"]["project_directory"]
        self._project_directory = project_dir
        project_root = os.path.dirname(os.path.dirname(project_dir))
        if project_root not in sys.path:
            sys.path.append(project_root)

        ResourceServer.ResourceLoader.set_project_root(project_dir)
        self.app = Kod.App(self.settings, editor_mode=True)
        self.app.configuration.editor_settings = self.editor_settings.editor_settings
        self.app.debug_renderer = DebugRenderingServer.DebugRenderingServer(self.app.configuration)
        self.app.renderer.debug_renderer = self.app.debug_renderer
        self.mode = EditorMode.EDIT
        self.commands = deque()

        loaded_scene = None

        self.camera = Nodes.Camera2D()
        self.app.set_camera(self.camera)
        if loaded_scene is not None:
            self.app.set_scene(loaded_scene)

        self.base_internal_width, self.base_internal_height = self.runtime_window_settings["internal_viewport_resolution"]
        self.width, self.height = self.base_internal_width, self.base_internal_height
        self.display_width, self.display_height = self.runtime_window_settings["viewport_resolution"]
        self.zoom_step = 1.1
        self.min_zoom = 0.1
        self.max_zoom = 12.0

        self.gizmo = EditorGizmoController(self)
        self.tools = EditorViewportToolController(self)
        self.overlay = EditorOverlayRenderer(self)
        self.ui = EditorUI(self, self.app)
        self.overlay_gizmo_nodes = []
        self._pick_bounds_handlers = {
            Nodes.Sprite2D: self._pick_bounds_sprite,
            Nodes.RectangleCollisionShape2D: self._pick_bounds_rectangle_collision,
            Nodes.Camera2D: self._pick_bounds_camera,
        }

        # Load editor state (last opened scene and zoom) after UI exists
        try:
            self._load_editor_state()
        except Exception:
            pass

    def _iter_ancestor_directories(self, start_path):
        path = os.path.abspath(start_path)
        while True:
            yield path
            parent = os.path.dirname(path)
            if parent == path:
                break
            path = parent

    def _default_project_directory(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "BeatSlash"))

    def _looks_like_project_directory(self, path):
        if not path:
            return False

        if not os.path.isdir(path):
            return False

        return os.path.isdir(os.path.join(path, "assets")) and os.path.isdir(os.path.join(path, "scenes"))

    def _discover_project_directory(self):
        configured = self.settings.project_settings.get("file_management", {}).get("project_directory")
        if self._looks_like_project_directory(configured):
            return os.path.abspath(configured)

        search_roots = [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]
        for root in search_roots:
            for ancestor in self._iter_ancestor_directories(root):
                persistent_dir = os.path.join(ancestor, ".project.kod")
                if os.path.isdir(persistent_dir):
                    return os.path.abspath(ancestor)

        return self._default_project_directory()

    def _project_data_dir(self):
        project_directory = self._project_directory or self.settings.project_settings["file_management"].get("project_directory")
        if not project_directory:
            project_directory = self._discover_project_directory()
        return os.path.join(os.path.abspath(project_directory), ".project.kod")

    def _project_settings_path(self):
        return os.path.join(self._project_data_dir(), "project_settings.json")

    def _editor_settings_path(self):
        return os.path.join(self._project_data_dir(), "editor_settings.json")

    def _editor_state_path(self):
        return os.path.join(self._project_data_dir(), "editor_state.json")

    def _load_settings_file(self, path):
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as file_handle:
                return json.load(file_handle)
        except Exception:
            return None

    def _save_settings_file(self, path, data):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as file_handle:
                json.dump(data, file_handle, indent=2)
            return True
        except Exception:
            return False

    def _load_persistent_settings(self):
        project_settings = self._load_settings_file(self._project_settings_path())
        if project_settings is None:
            legacy_project_settings_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")), ".kod_project_settings.json")
            project_settings = self._load_settings_file(legacy_project_settings_path)

        if isinstance(project_settings, dict):
            _merge_settings_dict(self.settings.project_settings, project_settings)

        editor_settings = self._load_settings_file(self._editor_settings_path())
        if editor_settings is None:
            legacy_editor_settings_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")), ".kod_editor_settings.json")
            editor_settings = self._load_settings_file(legacy_editor_settings_path)

        if isinstance(editor_settings, dict):
            _merge_settings_dict(self.editor_settings.editor_settings, editor_settings)

        project_dir = self.settings.project_settings.setdefault("file_management", {}).get("project_directory")
        if self._looks_like_project_directory(project_dir):
            resolved_project_dir = os.path.abspath(project_dir)
        else:
            resolved_project_dir = self._discover_project_directory()

        self.settings.project_settings["file_management"]["project_directory"] = resolved_project_dir
        self._project_directory = resolved_project_dir

        self._normalize_project_settings_paths()

    def _normalize_project_settings_paths(self):
        project_dir = self.settings.project_settings.get("file_management", {}).get("project_directory")
        if not project_dir:
            return

        runtime_settings = self.settings.project_settings.get("project", {})
        main_scene = runtime_settings.get("main_scene_path")
        if not main_scene or not isinstance(main_scene, str):
            return

        project_dir = os.path.abspath(project_dir)
        main_scene = os.path.normpath(main_scene)

        if os.path.isabs(main_scene):
            try:
                if os.path.commonpath([project_dir, main_scene]) == project_dir:
                    runtime_settings["main_scene_path"] = os.path.relpath(main_scene, project_dir)
            except Exception:
                return
            return

        legacy_prefix = os.path.join("src", "BeatSlash") + os.sep
        if main_scene.startswith(legacy_prefix):
            runtime_settings["main_scene_path"] = main_scene[len(legacy_prefix):]

    def save_settings(self):
        project_settings = copy.deepcopy(self.settings.project_settings)
        project_directory = project_settings.setdefault("file_management", {}).get("project_directory")
        if project_directory:
            project_directory = os.path.abspath(project_directory)
            project_settings["file_management"]["project_directory"] = project_directory
            self._project_directory = project_directory

        runtime_settings = project_settings.get("project", {})
        main_scene = runtime_settings.get("main_scene_path")
        if project_directory and isinstance(main_scene, str):
            main_scene = os.path.normpath(main_scene)
            if os.path.isabs(main_scene):
                try:
                    if os.path.commonpath([project_directory, main_scene]) == project_directory:
                        runtime_settings["main_scene_path"] = os.path.relpath(main_scene, project_directory)
                except Exception:
                    pass

        self._save_settings_file(self._project_settings_path(), project_settings)
        self._save_settings_file(self._editor_settings_path(), self.editor_settings.editor_settings)

        try:
            ResourceServer.ResourceLoader.set_project_root(
                self.settings.project_settings["file_management"]["project_directory"]
            )
        except Exception:
            pass

    def _screen_to_world(self, screen_x, screen_y):
        zoom = self._get_camera_zoom()
        return (
            (screen_x - self.width / 2.0) / zoom + self.camera.global_position[0] - self.camera.offset[0],
            (screen_y - self.height / 2.0) / zoom + self.camera.global_position[1] - self.camera.offset[1],
        )

    def _world_to_screen(self, world_x, world_y):
        zoom = self._get_camera_zoom()
        return (
            (world_x - self.camera.global_position[0] + self.camera.offset[0]) * zoom + self.width / 2.0,
            (world_y - self.camera.global_position[1] + self.camera.offset[1]) * zoom + self.height / 2.0,
        )

    def _get_camera_zoom(self):
        zoom = getattr(self.camera, "zoom", 1.0)
        if isinstance(zoom, (list, tuple)):
            zoom = zoom[0] if len(zoom) > 0 else 1.0
        try:
            zoom = float(zoom)
        except Exception:
            zoom = 1.0
        return max(0.001, zoom)

    def _set_camera_zoom(self, value):
        try:
            value = float(value)
        except Exception:
            return
        self.camera.zoom = max(self.min_zoom, min(self.max_zoom, value))

    def to_relative_path(self, path_str):
        if not isinstance(path_str, str):
            return path_str

        try:
            project_directory = self.settings.project_settings["file_management"]["project_directory"]
            if not path_str or not os.path.isabs(path_str):
                return path_str
            return os.path.relpath(path_str, project_directory)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to convert to relative path {e}")

        return path_str

    def render_frame(self):
        if not self.app.screen:
            ErrorHandler.throw_error("No screen supplied. Stopping rendering")
            return None

        selection_settings = self.app.configuration.editor_settings.setdefault("selection", {})
        selected_node = getattr(self.ui.state, "selected_node", None)
        selection_settings["selected_node_id"] = id(selected_node) if selected_node is not None else None

        self.overlay.queue_debug_overlays(self.overlay_gizmo_nodes)

        node_buckets = self.app.distribute_node_buckets() or {}
        renderable_nodes = node_buckets.get("rendering", [])
        ui_nodes = node_buckets.get("ui", [])

        self.app.renderer.render_frame(self.app.current_scene, self.camera, renderable_nodes)

        viewport_size = (int(self.display_width), int(self.display_height))
        composite_surface = pygame.Surface(viewport_size, pygame.SRCALPHA).convert_alpha()
        if self.app.internal_surface.get_size() != viewport_size:
            self.app.scaled_surface = pygame.transform.scale(self.app.internal_surface, viewport_size)
        else:
            self.app.scaled_surface = self.app.internal_surface.copy()

        composite_surface.blit(self.app.scaled_surface, (0, 0))

        self.app.renderer.render_ui_frame(
            ui_nodes,
            viewport_size=viewport_size,
            target_surface=composite_surface,
            source_size=self.app.internal_resolution
        )

        if self.app.screen:
            self.app.screen.blit(composite_surface, (0, 0))

        self.app.clock.tick(self.app.FPS)

        data = pygame.surfarray.array3d(composite_surface)
        data = data.transpose([1, 0, 2])
        frame_height, frame_width = data.shape[:2]
        alpha = np.full((frame_height, frame_width, 1), 255, dtype=np.uint8)
        rgba = np.concatenate((data, alpha), axis=2)
        return rgba.astype(np.float32) / 255.0

    def _collect_nodes(self, node, out=None):
        if out is None:
            out = []

        out.append(node)
        for child in getattr(node, "_children", []):
            self._collect_nodes(child, out)

        return out

    def _pick_bounds_sprite(self, node):
        image = node.image
        if image is None:
            return None

        return (
            node.global_position[0] + node.offset[0],
            node.global_position[1] + node.offset[1],
            image.get_width(),
            image.get_height(),
        )

    def _pick_bounds_rectangle_collision(self, node):
        return (
            node.global_position[0],
            node.global_position[1],
            float(node.size[0]),
            float(node.size[1]),
        )

    def _pick_bounds_camera(self, node):
        viewport_w, viewport_h = self.base_internal_width, self.base_internal_height
        zoom = getattr(node, "zoom", 1.0)
        if isinstance(zoom, (list, tuple)):
            zoom = zoom[0] if len(zoom) > 0 else 1.0
        try:
            zoom = float(zoom)
        except Exception:
            zoom = 1.0
        zoom = max(0.001, zoom)

        world_w = float(viewport_w) / zoom
        world_h = float(viewport_h) / zoom

        return (
            node.global_position[0] - node.offset[0] - world_w / 2.0,
            node.global_position[1] - node.offset[1] - world_h / 2.0,
            world_w,
            world_h,
        )

    def _pick_bounds_default(self, node):
        return (
            node.global_position[0] - 4.0,
            node.global_position[1] - 4.0,
            8.0,
            8.0,
        )

    def _get_pick_bounds(self, node):
        if not isinstance(node, Nodes.Node2D):
            return None

        for node_cls, handler in self._pick_bounds_handlers.items():
            if isinstance(node, node_cls):
                return handler(node)

        return self._pick_bounds_default(node)

    def _pick_node_at_world(self, world_x, world_y):
        scene = getattr(self.app, "current_scene", None)
        root = getattr(scene, "root", None)
        if root is None:
            return None

        ordered_nodes = self._collect_nodes(root, out=[])
        ordered_nodes = [node for node in ordered_nodes if isinstance(node, Nodes.Node2D)]
        ordered_nodes.sort(key=lambda node: getattr(node, "z_index", 0))

        for node in reversed(ordered_nodes):
            bounds = self._get_pick_bounds(node)
            if bounds is None:
                continue

            bx, by, bw, bh = bounds
            if bx <= world_x <= (bx + bw) and by <= world_y <= (by + bh):
                return node

        return None

    def _collect_overlay_gizmo_nodes(self, node, out=None):
        if out is None:
            out = []

        if self.overlay.should_draw_without_selection(node):
            out.append(node)

        for child in getattr(node, "_children", []):
            self._collect_overlay_gizmo_nodes(child, out)

        return out

    def _update_node(self, node, delta):
        node.editor_update(delta)

        if getattr(node, "_queued_for_deletion", False):
            if self.app.current_scene and node not in self.app.current_scene.deletion_queue:
                self.app.current_scene.deletion_queue.append(node)

        for child in getattr(node, "_children", []):
            self._update_node(child, delta)

    def _compute_frame_delta(self, last_frame_time):
        now = pygame.time.get_ticks()
        delta = (now - last_frame_time) / 1000.0
        return delta, now

    def _set_selected_node(self, node):
        self.ui.state.selected_node = node

        for tag, tag_node in list(self.ui.state.selectables.items()):
            if pygui.does_item_exist(tag):
                pygui.set_value(tag, node is not None and tag_node is node)

        if node is None:
            self.ui.inspector.clear()
            if pygui.does_item_exist("add_node_btn"):
                pygui.configure_item("add_node_btn", enabled=False)
            return

        self.ui.inspector.update(node)
        if pygui.does_item_exist("add_node_btn"):
            pygui.configure_item("add_node_btn", enabled=True)

    def get_selected_paint_tile_id(self, node):
        return self.ui.state.selected_paint_tile_ids.get(id(node))

    def set_selected_paint_tile_id(self, node, tile_id: int):
        self.ui.state.selected_paint_tile_ids[id(node)] = int(tile_id)

    def get_selected_paint_tile_layer(self, node):
        selected_layer = self.ui.state.selected_paint_tile_layers.get(id(node), 0)
        if isinstance(node, Nodes.TileMap2D):
            try:
                setattr(node, "_editor_active_paint_layer", int(selected_layer))
            except Exception:
                setattr(node, "_editor_active_paint_layer", 0)
        return selected_layer

    def set_selected_paint_tile_layer(self, node, layer_index: int):
        normalized_layer = int(layer_index)
        self.ui.state.selected_paint_tile_layers[id(node)] = normalized_layer
        if isinstance(node, Nodes.TileMap2D):
            setattr(node, "_editor_active_paint_layer", normalized_layer)

    def get_scene_hierarchy(self):
        root = getattr(self.app.current_scene, "root", None)
        if root is None:
            return {}

        def build(node):
            return {child: build(child) for child in getattr(node, "_children", [])}

        return {root: build(root)}

    def _compute_editor_internal_resolution(self, display_width, display_height):
        display_width = max(1, int(display_width))
        display_height = max(1, int(display_height))

        base_w = max(1, int(self.base_internal_width))
        base_h = max(1, int(self.base_internal_height))

        display_aspect = display_width / float(display_height)
        base_aspect = base_w / float(base_h)

        if display_aspect < base_aspect:
            # Narrow viewport: keep horizontal extent and expand vertical extent.
            target_w = base_w
            target_h = max(1, int(round(base_w / display_aspect)))
        else:
            # Wide viewport: keep vertical extent and expand horizontal extent.
            target_h = base_h
            target_w = max(1, int(round(base_h * display_aspect)))

        return target_w, target_h

    def update_viewport_size(self, new_width, new_height):
        new_width, new_height = int(new_width), int(new_height)
        if new_width <= 0 or new_height <= 0:
            return False, False

        display_changed = not (new_width == self.display_width and new_height == self.display_height)
        target_internal_width, target_internal_height = self._compute_editor_internal_resolution(new_width, new_height)
        internal_changed = not (target_internal_width == self.width and target_internal_height == self.height)

        if not display_changed and not internal_changed:
            return False, False

        self.display_width, self.display_height = new_width, new_height
        self.app.resolution = (self.display_width, self.display_height)

        if internal_changed:
            self.width, self.height = target_internal_width, target_internal_height
            self.app.internal_resolution = (self.width, self.height)
            new_surface = pygame.Surface((self.width, self.height)).convert_alpha()
            self.app.internal_surface = new_surface
            self.app.renderer.screen = new_surface

        self.runtime_window_settings["viewport_resolution"] = (self.display_width, self.display_height)
        self.runtime_window_settings["internal_viewport_resolution"] = (self.width, self.height)

        return True, internal_changed

    def queue_command(self, command_type, **payload):
        if isinstance(command_type, str):
            try:
                command_type = EditorCommandType(command_type)
            except Exception:
                ErrorHandler.throw_error(f"Unknown editor command: {command_type}")
                return

        self.commands.append(EditorCommand(type=command_type, payload=payload))

    def save_scene(self, scene=None, scene_path=None):
        if scene is None:
            scene = self.app.current_scene
        if scene_path is None:
            scene_path = getattr(scene, "path", None) if scene else None

        try:
            if ResourceServer.SceneLoader.save(scene, scene_path):
                ErrorHandler.throw_info(f"Scene saved successfully: {scene_path}")
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to save scene to {scene_path}, {e}")

    def load_scene(self, scene_path, save_state=True):
        if scene_path is None:
            ErrorHandler.throw_error("Failed to load scene from None")

        try:
            new_scene = ResourceServer.SceneLoader.load(scene_path)
            self.app.set_scene(new_scene)
            self.ui.state.selected_node = None
            self.ui.state.selected_paint_tile_ids.clear()
            self.ui.state.selected_paint_tile_layers.clear()
            self.ui.inspector.clear()
            self.ui._update_hierarchy()
            self.ui.menubar.update()
            try:
                loaded_path = getattr(new_scene, "path", None) or scene_path
                self.ui.viewport.register_scene(loaded_path, make_active=True)
            except Exception:
                pass

            if save_state and not getattr(self, "_restoring_state", False):
                try:
                    self._save_editor_state()
                except Exception:
                    pass

        except Exception as e:
            ErrorHandler.throw_error(f"Error occured loading scene: {scene_path}, {e}")

    def _state_file_path(self):
        return self._editor_state_path()

    def _load_editor_state(self):
        path = self._state_file_path()
        if not os.path.exists(path):
            return False
        try:
            self._restoring_state = True
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            last_zoom = data.get("last_zoom")
            last_scene = data.get("last_opened_scene")
            saved_tabs = data.get("open_scene_tabs") or []
            saved_active = data.get("active_scene_path")
            
            window_width = data.get("window_width")
            window_height = data.get("window_height")
            window_pos = data.get("window_pos")

            if window_width and window_height:
                try:
                    if pygui.is_viewport_ok():
                        pygui.set_viewport_width(int(window_width))
                        pygui.set_viewport_height(int(window_height))
                        if window_pos and len(window_pos) == 2:
                            pygui.set_viewport_pos(window_pos)
                except Exception:
                    pass

            if last_zoom is not None:
                try:
                    self._set_camera_zoom(float(last_zoom))
                except Exception:
                    pass

            if last_scene:
                try:
                    resolved = ResourceServer.ResourceLoader.resolve_path(last_scene)
                    if os.path.exists(resolved):
                        self.load_scene(resolved, save_state=False)
                except Exception:
                    pass

            if hasattr(self, "ui") and hasattr(self.ui, "viewport"):
                try:
                    resolved_tabs = []
                    for tab_path in saved_tabs:
                        if not tab_path:
                            continue
                        resolved = ResourceServer.ResourceLoader.resolve_path(tab_path)
                        if os.path.exists(resolved):
                            resolved_tabs.append(resolved)
                            self.ui.viewport.register_scene(resolved, make_active=False, refresh_ui=False)

                    if saved_active:
                        resolved_active = ResourceServer.ResourceLoader.resolve_path(saved_active)
                        if os.path.exists(resolved_active):
                            self.ui.viewport.set_active_scene(resolved_active)
                    
                    self.ui.viewport.build_tabs()
                except Exception:
                    pass


            return True
        except Exception:
            return False
        finally:
            self._restoring_state = False

    def _save_editor_state(self):
        path = self._state_file_path()
        data = {}
        
        try:
            if pygui.is_viewport_ok():
                data["window_width"] = pygui.get_viewport_width()
                data["window_height"] = pygui.get_viewport_height()
                data["window_pos"] = pygui.get_viewport_pos()
        except Exception:
            pass
            
        try:
            data["last_zoom"] = self._get_camera_zoom()
        except Exception:
            data["last_zoom"] = None

        try:
            scene_path = getattr(self.app.current_scene, "path", None)
            if scene_path:
                # store relative when possible
                data["last_opened_scene"] = self.to_relative_path(scene_path)
            else:
                data["last_opened_scene"] = None
        except Exception:
            data["last_opened_scene"] = None

        try:
            tabs = getattr(self.ui.state, "open_scene_tabs", []) if hasattr(self, "ui") else []
            active_tab = getattr(self.ui.state, "active_scene_path", None) if hasattr(self, "ui") else None
            data["open_scene_tabs"] = [self.to_relative_path(p) for p in tabs if p]
            data["active_scene_path"] = self.to_relative_path(active_tab) if active_tab else None
        except Exception:
            data["open_scene_tabs"] = []
            data["active_scene_path"] = None

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    def run_scene(self, scene_path=None):
        # This needs to run in a subprocess to avoid freezing the editor.
        try:
            if scene_path is None:
                ErrorHandler.throw_error("No scene path available to run")
                return

            scene_path = os.path.abspath(scene_path)
            if not ResourceServer.SceneLoader.save(self.app.current_scene, scene_path):
                ErrorHandler.throw_error(f"Failed to save scene before running: {scene_path}")
                return

            ErrorHandler.throw_info(f"Starting scene: {scene_path}...")
            editor_file = os.path.abspath(__file__)
            src_root = os.path.dirname(os.path.dirname(os.path.dirname(editor_file)))

            env = os.environ.copy()
            if "SDL_VIDEODRIVER" in env:
                del env["SDL_VIDEODRIVER"]

            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "KodEngine.editor.subprocess.runtime",
                    "--scene",
                    scene_path,
                    "--project-settings-json",
                    json.dumps(self._runtime_project_settings()),
                    "--editor-settings-json",
                    json.dumps(self.editor_settings.editor_settings),
                ],
                cwd=src_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            debug(f"Runtime started PID: {process.pid}")

            def read_output(proc):
                try:
                    for line in proc.stdout:
                        if line:
                            print(f"[RUNTIME] {line.strip()}")
                            traceback.print_exc()
                            sys.stdout.flush()

                    for line in proc.stderr:
                        if line:
                            print(f"[RUNTIME ERROR] {line.strip()}")
                            traceback.print_exc()
                            sys.stdout.flush()

                except Exception as e:
                    print("[KodEditor ERROR]")
                    traceback.print_exc()

            import threading
            threading.Thread(target=read_output, args=(process,), daemon=True).start()

            ErrorHandler.throw_success(f"Scene started (PID: {process.pid})")

        except Exception as e:
            ErrorHandler.throw_error(f"Failed to run scene: {e}")

    def run_project(self):
        try:
            current_scene = getattr(self.app, "current_scene", None)
            current_path = getattr(current_scene, "path", None) if current_scene else None
            if current_scene and current_path:
                self.save_scene(scene=current_scene, scene_path=current_path)

            main_scene_file_path = self.app.configuration.project_settings["project"]["main_scene_path"]
            self.run_scene(main_scene_file_path)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to run project: {e}")

    def _runtime_project_settings(self):
        return copy.deepcopy(self.settings.project_settings)

    def drag_file(self):
        pass

    def open_file(self, file_path):
        extension_command_list = self.settings.editor_settings["file_management"]["file_extension_commands"]

        _, extension = os.path.splitext(file_path)
        command = extension_command_list.get(extension, "--default")

        match command:
            case "--editor":
                if file_path.endswith(".kscn"):
                    self.load_scene(file_path)

            case "--default":
                try:
                    if platform.system() == "Windows":
                        os.startfile(file_path)  # type: ignore
                    elif platform.system() == "Darwin":
                        subprocess.run(["open", file_path])
                    else:
                        subprocess.run(["xdg-open", file_path])
                except Exception as e:
                    ErrorHandler.throw_error(f"Failed to open file {file_path}: {e}")

    def on_mouse_wheel(self, wheel_delta):
        if hasattr(self, "ui") and self.ui.dialogs.is_any_dialog_open():
            return
        self.gizmo.on_mouse_wheel(wheel_delta)

    def _dispatch_command(self, cmd: EditorCommand):
        match cmd.type:
            case EditorCommandType.SAVE_SCENE:
                self.save_scene()
            case EditorCommandType.LOAD_SCENE:
                self.load_scene(cmd.payload.get("path"))
            case EditorCommandType.RUN_SCENE:
                self.run_scene(cmd.payload.get("scene_path"))
            case EditorCommandType.RUN_PROJECT:
                self.run_project()
            case EditorCommandType.OPEN_FILE:
                file_path = cmd.payload.get("file_path")
                if file_path:
                    self.open_file(file_path)
            case EditorCommandType.OPEN_EDITOR_SETTINGS:
                self.ui.dialogs.show_settings_window(self.editor_settings.editor_settings, "Editor Settings")
            case EditorCommandType.OPEN_PROJECT_SETTINGS:
                self.ui.dialogs.show_settings_window(self.app.configuration.project_settings, "Project Settings")
            case EditorCommandType.OPEN_EXPORT:
                self.ui.dialogs.show_export_window()

            case EditorCommandType.COPY_NODE:
                self.ui.state.copied_node_data = None
                selected_node = getattr(self.ui.state, "selected_node", None)
                if selected_node is not None:
                    try:
                        self.ui.state.copied_node_data = selected_node.clone()
                    except Exception as e:
                        ErrorHandler.throw_error(f"Failed to copy node: {e}")
            
            case EditorCommandType.PASTE_NODE:
                if self.ui.state.copied_node_data is not None:
                    try:
                        new_node = self.ui.state.copied_node_data
                        parent_node = getattr(self.ui.state.selected_node, "_parent", None)
                        if parent_node is not None:
                            parent_node.add_child(new_node)
                            self._set_selected_node(new_node)
                            self.ui._update_hierarchy()
                        else:
                            ErrorHandler.throw_error("Cannot paste node: No parent found for the new node.")
                    except Exception as e:
                        ErrorHandler.throw_error(f"Failed to paste node: {e}")
            
            case EditorCommandType.DUPLICATE_NODE:
                selected_node = getattr(self.ui.state, "selected_node", None)
                if selected_node is not None:
                    try:
                        new_node = selected_node.clone()
                        parent_node = getattr(selected_node, "_parent", None)
                        if parent_node is not None:
                            parent_node.add_child(new_node)
                            self._set_selected_node(new_node)
                            self.ui._update_hierarchy()
                        else:
                            ErrorHandler.throw_error("Cannot duplicate node: No parent found for the new node.")
                    except Exception as e:
                        ErrorHandler.throw_error(f"Failed to duplicate node: {e}")

    def _drain_commands(self):
        while self.commands:
            cmd = self.commands.popleft()
            self._dispatch_command(cmd)

    def _handle_keyboard_shortcuts(self):
        if self.ui.dialogs.is_any_dialog_open():
            return

        for action, shortcut in self.editor_settings.editor_settings["keyboard_shortcuts"].items():
            modifiers = shortcut.get("modifiers", [])
            key = shortcut.get("key")

            ctrl_pressed = pygui.is_key_down(pygui.mvKey_ModCtrl)
            shift_pressed = pygui.is_key_down(pygui.mvKey_ModShift)
            alt_pressed = pygui.is_key_down(pygui.mvKey_ModAlt)

            key_code = getattr(pygui, f"mvKey_{key.upper()}", None)
            if (
                (("ctrl" in modifiers) == ctrl_pressed) and
                (("shift" in modifiers) == shift_pressed) and
                (("alt" in modifiers) == alt_pressed) and
                key_code is not None and pygui.is_key_pressed(key_code)
            ):
                match action:
                    case "save_scene":
                        self.queue_command(EditorCommandType.SAVE_SCENE)
                    case "load_scene":
                        self.queue_command(EditorCommandType.LOAD_SCENE)
                    case "run_scene":
                        self.queue_command(EditorCommandType.RUN_SCENE, scene_path=getattr(self.app.current_scene, "path", None))
                    case "run_project":
                        self.queue_command(EditorCommandType.RUN_PROJECT)
                    case "open_editor_settings":
                        self.queue_command(EditorCommandType.OPEN_EDITOR_SETTINGS)
                    case "duplicate_node":
                        self.queue_command(EditorCommandType.DUPLICATE_NODE)
                    case "copy_node":
                        self.queue_command(EditorCommandType.COPY_NODE)
                    case "paste_node":
                        self.queue_command(EditorCommandType.PASTE_NODE)

    def update_events(self):
        self._drain_commands()

        if self.ui.dialogs.is_any_dialog_open():
            self.gizmo.cancel_interaction()
            self.tools.reset()
            return

        self.gizmo.update_interaction()
        self.tools.update()

        self._handle_keyboard_shortcuts()

        if pygui.is_mouse_button_clicked(pygui.mvMouseButton_Left):
            if not self.gizmo._is_mouse_over_viewport():
                return

            if self.tools.click_consumed:
                return

            if self.gizmo.drag_active:
                return

            mouse_screen = self.gizmo._viewport_mouse_screen_position()
            if mouse_screen is None:
                return

            world_x, world_y = self._screen_to_world(mouse_screen[0], mouse_screen[1])
            picked_node = self._pick_node_at_world(world_x, world_y)
            self._set_selected_node(picked_node)

    def _prepare_editor_frame(self):
        if not self.app.running:
            self.ui.check_resize()


    def _update_editor_scene_state(self, delta):
        root = getattr(self.app.current_scene, "root", None)
        if root is None:
            self.overlay_gizmo_nodes = []
            return

        self._update_node(root, delta)
        self.overlay_gizmo_nodes = self._collect_overlay_gizmo_nodes(root, out=[])

    def _sync_editor_scene_deletions(self):
        if not self.app.current_scene:
            return

        nodes_were_deleted = self.app.current_scene._process_deletion_queue()
        if nodes_were_deleted and hasattr(self, "ui"):
            self.ui._update_hierarchy()

    def _render_editor_viewport_frame(self):
        if self.app.running:
            return

        frame = self.render_frame()
        self.ui.push_frame(frame)

    def _run_editor_frame(self, delta):
        self.update_events()
        
        self._prepare_editor_frame()
        self._update_editor_scene_state(delta)

        if self.app.current_scene:
            self.app.current_scene._process_ui(self.app.internal_resolution)
        
        self._sync_editor_scene_deletions()
        self._render_editor_viewport_frame()
        

    def run(self):
        last_frame_time = pygame.time.get_ticks()

        while pygui.is_dearpygui_running():
            delta, last_frame_time = self._compute_frame_delta(last_frame_time)
            self._run_editor_frame(delta)
            pygui.render_dearpygui_frame()

        self._save_editor_state()
        self.save_settings()
        pygui.destroy_context()

def main():
    editor = KodEditor()
    editor.run()

if __name__ == "__main__":
    main()

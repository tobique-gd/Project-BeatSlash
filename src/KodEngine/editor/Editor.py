# GENERAL IMPORTS
import os
import sys
import platform
import subprocess
from collections import deque

import dearpygui.dearpygui as pygui
import numpy as np
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
            }
        }




class KodEditor:
    def __init__(self):
        ErrorHandler.set_editor_mode(True)
        self.settings = Kod.Settings()
        self.editor_settings = EditorSettings()
        self.initial_res = (640, 360)
        self.settings.project_settings["window"]["internal_viewport_resolution"] = self.initial_res

        current_dir = os.path.dirname(os.path.abspath(__file__))
        potential_path = os.path.abspath(os.path.join(current_dir, "..", "..", "BeatSlash"))
        if os.path.exists(potential_path):
            project_dir = potential_path
            sys.path.append(os.path.dirname(potential_path))

        self.settings.project_settings["file_management"]["project_directory"] = project_dir

        ResourceServer.ResourceLoader.set_project_root(project_dir)
        self.app = Kod.App(self.settings, editor_mode=True)
        self.app.configuration.editor_settings = self.editor_settings.editor_settings["debug"]
        self.app.debug_renderer = DebugRenderingServer.DebugRenderingServer(self.app.configuration)
        self.app.renderer.debug_renderer = self.app.debug_renderer
        self.mode = EditorMode.EDIT
        self.commands = deque()

        scene_path = os.path.join(project_dir, "scenes", "world.kscn")
        loaded_scene = ResourceServer.SceneLoader.load(scene_path)

        self.camera = Nodes.Camera2D()
        self.app.set_camera(self.camera)
        self.app.set_scene(loaded_scene)

        self.width, self.height = self.initial_res
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

        self.overlay.queue_debug_overlays(self.overlay_gizmo_nodes)

        self.app.renderer.render_frame(self.app.current_scene, self.camera)
        self.app.scaled_surface = pygame.transform.scale(self.app.internal_surface, self.app.resolution)
        self.app.screen.blit(self.app.scaled_surface, (0, 0))

        self.app.clock.tick(self.app.FPS)

        data = pygame.surfarray.array3d(self.app.internal_surface)
        data = data.transpose([1, 0, 2])
        alpha = np.full((self.height, self.width, 1), 255, dtype=np.uint8)
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
        return (
            node.global_position[0] - node.offset[0] - self.initial_res[0] / 2.0,
            node.global_position[1] - node.offset[1] - self.initial_res[1] / 2.0,
            float(self.initial_res[0]),
            float(self.initial_res[1]),
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

    def get_scene_hierarchy(self):
        root = getattr(self.app.current_scene, "root", None)
        if root is None:
            return {}

        def build(node):
            return {child: build(child) for child in getattr(node, "_children", [])}

        return {root: build(root)}

    def update_viewport_size(self, new_width, new_height):
        new_width, new_height = int(new_width), int(new_height)
        if new_width == self.width and new_height == self.height:
            return False
        if new_width <= 0 or new_height <= 0:
            return False

        self.width, self.height = new_width, new_height

        self.app.internal_resolution = (self.width, self.height)
        self.settings.project_settings["window"]["internal_viewport_resolution"] = (self.width, self.height)

        new_surface = pygame.Surface((self.width, self.height)).convert_alpha()
        self.app.internal_surface = new_surface
        self.app.renderer.screen = new_surface
        return True

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
            ResourceServer.SceneLoader.save(scene, scene_path)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to save scene to {scene_path}, {e}")

    def load_scene(self, scene_path):
        if scene_path is None:
            ErrorHandler.throw_error("Failed to load scene from None")

        try:
            new_scene = ResourceServer.SceneLoader.load(scene_path)
            self.app.set_scene(new_scene)
            self.ui.state.selected_node = None
            self.ui.state.selected_paint_tile_ids.clear()
            self.ui.inspector.clear()
            self.ui._update_hierarchy()
            self.ui.menubar.update()
        except Exception as e:
            ErrorHandler.throw_error(f"Error occured loading scene: {scene_path}, {e}")

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

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "KodEngine.editor.subprocess.runtime",
                    "--scene",
                    scene_path,
                ],
                cwd=src_root,
                env=env,
            )

            if result.returncode != 0:
                ErrorHandler.throw_error(f"Scene process exited with code {result.returncode}")

        except Exception as e:
            ErrorHandler.throw_error(f"Failed to run scene: {e}")

    def drag_file(self):
        pass

    def open_file(self, file_path):
        extension_command_list = self.settings.project_settings["file_management"]["file_extension_commands"]

        _, extension = os.path.splitext(file_path)
        command = extension_command_list.get(extension, "--default")

        match command:
            case "--editor":
                if file_path.endswith(".kscn"):
                    self.load_scene(file_path)

            case "--default":
                try:
                    if platform.system() == "Windows":
                        os.startfile(file_path)  # type: ignore # IGNORE
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
                main_scene_file_path = self.app.configuration.project_settings["runtime"]["main_scene_path"]
                self.run_scene(main_scene_file_path)
            case EditorCommandType.OPEN_FILE:
                file_path = cmd.payload.get("file_path")
                if file_path:
                    self.open_file(file_path)
            case EditorCommandType.OPEN_EDITOR_SETTINGS:
                self.ui.dialogs.show_editor_settings_window()

    def _drain_commands(self):
        while self.commands:
            cmd = self.commands.popleft()
            self._dispatch_command(cmd)

    def update_events(self):
        self._drain_commands()

        if self.ui.dialogs.is_any_dialog_open():
            self.gizmo.cancel_interaction()
            self.tools.reset()
            return

        self.gizmo.update_interaction()
        self.tools.update()

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
        self._sync_editor_scene_deletions()
        self._render_editor_viewport_frame()
        

    def run(self):
        last_frame_time = pygame.time.get_ticks()

        while pygui.is_dearpygui_running():
            delta, last_frame_time = self._compute_frame_delta(last_frame_time)
            self._run_editor_frame(delta)
            pygui.render_dearpygui_frame()

        pygui.destroy_context()

def main():
    editor = KodEditor()
    editor.run()

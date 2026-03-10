#GENERAL IMPORTY
import dearpygui.dearpygui as pygui
import numpy as np
import pygame
import os
import sys
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto

#i need to run this in a dummy environment to eliminate event overlaps between dpg and pygame
os.environ["SDL_VIDEODRIVER"] = "dummy"

#EDITOR IMPORTS
from . import ui_components as UIComp
from . import DebugRenderingServer

#ENGINE IMPORTS
from ..engine import Kod, Nodes, ResourceServer
from ..engine.ErrorHandler import ErrorHandler


class EditorMode(Enum):
    EDIT = auto()
    PLAYTEST = auto()
    PAUSED = auto()


@dataclass
class EditorCommand:
    type: str
    payload: dict


class KodEditor:
    def __init__(self):
        ErrorHandler.set_editor_mode(True)
        self.settings = Kod.Settings()
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
        self.app.debug_renderer = DebugRenderingServer.DebugRenderingServer(self.settings)
        self.app.renderer.debug_renderer = self.app.debug_renderer
        self.mode = EditorMode.EDIT
        self.commands = deque()

        scene_path = os.path.join(project_dir, "scenes", "world.kscn")
        loaded_scene = ResourceServer.SceneLoader.load(scene_path)

        self.camera = Nodes.Camera2D()
        
        self.app.set_camera(self.camera)
        self.app.set_scene(loaded_scene)

        self.width, self.height = self.initial_res
        self._gizmo_drag_active = False
        self._gizmo_drag_axis = None
        self._gizmo_drag_start_mouse_screen = (0.0, 0.0)
        self._gizmo_drag_start_node_world = (0.0, 0.0)
        self._left_mouse_was_down = False
        self._gizmo_hover_axis = None
        self.zoom_step = 1.1
        self.min_zoom = 0.2
        self.max_zoom = 12.0
        self.ui = EditorUI(self, self.app)

    def queue_command(self, command_type, **payload):
        self.commands.append(EditorCommand(type=command_type, payload=payload))

    def _dispatch_command(self, cmd: EditorCommand):
        if cmd.type == "save_scene":
            self.save_scene()
        elif cmd.type == "load_scene":
            self.load_scene(cmd.payload.get("path"))
        elif cmd.type == "run_scene":
            self.run_scene(cmd.payload.get("scene_path"))

    def _drain_commands(self):
        while self.commands:
            cmd = self.commands.popleft()
            self._dispatch_command(cmd)

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
        return max(0.05, zoom)

    def _set_camera_zoom(self, value):
        try:
            value = float(value)
        except Exception:
            return
        self.camera.zoom = max(self.min_zoom, min(self.max_zoom, value))

    def _get_gizmo_spacing_scale(self):
        return max(1.0, self._get_camera_zoom())

    def _is_mouse_over_viewport(self):
        if not pygui.does_item_exist("viewport_image"):
            return False

        try:
            mouse_x, mouse_y = pygui.get_mouse_pos(local=False)
            rect_min_x, rect_min_y = pygui.get_item_rect_min("viewport_image")
            rect_w, rect_h = pygui.get_item_rect_size("viewport_image")
        except Exception:
            return False

        if rect_w <= 0 or rect_h <= 0:
            return False

        local_x = mouse_x - rect_min_x
        local_y = mouse_y - rect_min_y
        return 0 <= local_x <= rect_w and 0 <= local_y <= rect_h

    def on_mouse_wheel(self, wheel_delta):
        if not self._is_mouse_over_viewport():
            return

        if self._gizmo_drag_active:
            return

        if isinstance(wheel_delta, (list, tuple)):
            if len(wheel_delta) == 0:
                return
            wheel_delta = wheel_delta[0]

        try:
            delta = float(wheel_delta)
        except Exception:
            return

        if abs(delta) < 0.0001:
            return

        before_mouse_world = self._viewport_mouse_world_position()
        if before_mouse_world is None:
            return

        current_zoom = self._get_camera_zoom()
        new_zoom = current_zoom * (self.zoom_step ** delta)
        self._set_camera_zoom(new_zoom)

        after_mouse_world = self._viewport_mouse_world_position()
        if after_mouse_world is None:
            return

        cam_x, cam_y = self.camera.global_position
        shift_x = before_mouse_world[0] - after_mouse_world[0]
        shift_y = before_mouse_world[1] - after_mouse_world[1]
        self.camera.global_position = (cam_x + shift_x, cam_y + shift_y)

    def _viewport_mouse_world_position(self):
        if not pygui.does_item_exist("viewport_image"):
            return None

        try:
            mouse_x, mouse_y = pygui.get_mouse_pos(local=False)
            rect_min_x, rect_min_y = pygui.get_item_rect_min("viewport_image")
            rect_w, rect_h = pygui.get_item_rect_size("viewport_image")
        except Exception:
            return None

        if rect_w <= 0 or rect_h <= 0:
            return None

        local_x = mouse_x - rect_min_x
        local_y = mouse_y - rect_min_y

        if not self._gizmo_drag_active:
            if local_x < 0 or local_y < 0 or local_x > rect_w or local_y > rect_h:
                return None

        scaled_x = local_x * (self.width / float(rect_w))
        scaled_y = local_y * (self.height / float(rect_h))
        return self._screen_to_world(scaled_x, scaled_y)

    def _viewport_mouse_screen_position(self):
        if not pygui.does_item_exist("viewport_image"):
            return None

        try:
            mouse_x, mouse_y = pygui.get_mouse_pos(local=False)
            rect_min_x, rect_min_y = pygui.get_item_rect_min("viewport_image")
            rect_w, rect_h = pygui.get_item_rect_size("viewport_image")
        except Exception:
            return None

        if rect_w <= 0 or rect_h <= 0:
            return None

        local_x = mouse_x - rect_min_x
        local_y = mouse_y - rect_min_y

        if not self._gizmo_drag_active:
            if local_x < 0 or local_y < 0 or local_x > rect_w or local_y > rect_h:
                return None

        return (
            local_x * (self.width / float(rect_w)),
            local_y * (self.height / float(rect_h)),
        )

    def _pick_gizmo_axis(self, node_world_pos, mouse_screen_pos):
        nx, ny = node_world_pos
        mx, my = mouse_screen_pos
        sx, sy = self._world_to_screen(nx, ny)
        spacing_scale = self._get_gizmo_spacing_scale()

        def in_rect(x, y, w, h, pad=0.0):
            return (x - pad) <= mx <= (x + w + pad) and (y - pad) <= my <= (y + h + pad)

        x_axis_center_x = sx + 60.0 * spacing_scale
        x_axis_center_y = sy
        y_axis_center_x = sx
        y_axis_center_y = sy + 60.0 * spacing_scale
        xy_axis_center_x = sx + 30.0 * spacing_scale
        xy_axis_center_y = sy + 30.0 * spacing_scale
        if in_rect(xy_axis_center_x - 16.0, xy_axis_center_y - 16.0, 32.0, 32.0, pad=4.0) or in_rect(sx - 15.5, sy - 15.5, 31.0, 31.0, pad=4.0):
            return "xy"

        if in_rect(x_axis_center_x - 32.0, x_axis_center_y - 16.0, 64.0, 32.0, pad=4.0):
            return "x"

        if in_rect(y_axis_center_x - 16.0, y_axis_center_y - 32.0, 32.0, 64.0, pad=4.0):
            return "y"

        return None

    def _update_gizmo_cursor(self):
        set_cursor = getattr(pygui, "set_mouse_cursor", None)
        cursor_arrow = getattr(pygui, "mvMouseCursor_Arrow", None)
        cursor_resize_ew = getattr(pygui, "mvMouseCursor_ResizeEW", None)
        cursor_resize_ns = getattr(pygui, "mvMouseCursor_ResizeNS", None)
        cursor_resize_all = getattr(pygui, "mvMouseCursor_ResizeAll", None)

        node = self.ui.state.selected_node
        if not isinstance(node, Nodes.Node2D):
            self._gizmo_hover_axis = None
            return

        mouse_screen = self._viewport_mouse_screen_position()
        if mouse_screen is None or self._gizmo_drag_active:
            self._gizmo_hover_axis = None
            if set_cursor is not None:
                try:
                    if cursor_arrow is not None:
                        set_cursor(cursor_arrow)
                except Exception:
                    pass
            return

        axis = self._pick_gizmo_axis(node.global_position, mouse_screen)
        self._gizmo_hover_axis = axis

        if set_cursor is not None:
            try:
                if axis == "x":
                    if cursor_resize_ew is not None:
                        set_cursor(cursor_resize_ew)
                elif axis == "y":
                    if cursor_resize_ns is not None:
                        set_cursor(cursor_resize_ns)
                elif axis == "xy":
                    if cursor_resize_all is not None:
                        set_cursor(cursor_resize_all)
                else:
                    if cursor_arrow is not None:
                        set_cursor(cursor_arrow)
            except Exception:
                pass

    def _update_gizmo_interaction(self):
        node = self.ui.state.selected_node
        if not isinstance(node, Nodes.Node2D):
            self._gizmo_drag_active = False
            self._left_mouse_was_down = pygui.is_mouse_button_down(pygui.mvMouseButton_Left)
            return

        mouse_screen = self._viewport_mouse_screen_position()
        mouse_down = pygui.is_mouse_button_down(pygui.mvMouseButton_Left)
        just_pressed = mouse_down and not self._left_mouse_was_down
        just_released = (not mouse_down) and self._left_mouse_was_down

        if just_pressed and mouse_screen is not None:
            axis = self._pick_gizmo_axis(node.global_position, mouse_screen)
            if axis is not None:
                self._gizmo_drag_active = True
                self._gizmo_drag_axis = axis
                self._gizmo_drag_start_mouse_screen = mouse_screen
                self._gizmo_drag_start_node_world = node.global_position

        if self._gizmo_drag_active and mouse_screen is not None and mouse_down:
            start_mouse_x, start_mouse_y = self._gizmo_drag_start_mouse_screen
            start_node_x, start_node_y = self._gizmo_drag_start_node_world
            zoom = self._get_camera_zoom()
            delta_x = (mouse_screen[0] - start_mouse_x) / zoom
            delta_y = (mouse_screen[1] - start_mouse_y) / zoom

            new_x, new_y = start_node_x, start_node_y
            if self._gizmo_drag_axis in ("x", "xy"):
                new_x = start_node_x + delta_x
            if self._gizmo_drag_axis in ("y", "xy"):
                new_y = start_node_y + delta_y

            node.global_position = (new_x, new_y)

        if self._gizmo_drag_active and just_released:
            self._gizmo_drag_active = False
            self._gizmo_drag_axis = None
            self.ui.inspector.update(node)

        self._left_mouse_was_down = mouse_down
    
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

        self._queue_editor_debug_overlays()

        self.app.renderer.render_frame(self.app.current_scene, self.camera)
        self.app.scaled_surface = pygame.transform.scale(self.app.internal_surface, self.app.resolution)
        self.app.screen.blit(self.app.scaled_surface, (0, 0))

        self.app.clock.tick(self.app.FPS)
        
        data = pygame.surfarray.array3d(self.app.internal_surface)
        data = data.transpose([1, 0, 2])
        alpha = np.full((self.height, self.width, 1), 255, dtype=np.uint8)
        rgba = np.concatenate((data, alpha), axis=2)
        return rgba.astype(np.float32) / 255.0

    def _queue_editor_debug_overlays(self):
        if not hasattr(self.app, "debug_renderer"):
            return
        
        debug = self.app.debug_renderer
        if debug is None:
            return
        debug.clear_command_list()

        if self.ui.state.selected_node:
            node = self.ui.state.selected_node

            if not hasattr(node, "global_position"):
                return

            if isinstance(node, Nodes.Camera2D):
                viewport_w, viewport_h = self.ui.editor.initial_res
                debug.draw_rect(
                    (
                        node.global_position[0] - node.offset[0] - viewport_w / 2.0,
                        node.global_position[1] - node.offset[1] - viewport_h / 2.0,
                        viewport_w,
                        viewport_h,
                    ),
                    color=self.settings.editor_settings["default_gizmo_color"],
                    space="world"
                )
            
            if isinstance(node, Nodes.Sprite2D):
                if node.texture:
                    debug.draw_rect(
                        (
                            node.global_position[0] + node.offset[0],
                            node.global_position[1] + node.offset[1],
                            node.texture.get_width(),
                            node.texture.get_height(),
                        ),
                        color=self.settings.editor_settings["default_gizmo_color"],
                        space="world"
                    )
            
            if isinstance(node, Nodes.AnimatedSprite2D):
                if node.current_animation:
                    animation_texture = node.current_animation.get_current_frame_rect()

                    debug.draw_rect(
                        (
                            node.global_position[0] + node.offset[0],
                            node.global_position[1] + node.offset[1],
                            animation_texture.size[0],
                            animation_texture.size[1],
                        ),
                        color=self.settings.editor_settings["default_gizmo_color"],
                        space="world"
                    )
            
            if isinstance(node, Nodes.RectangleCollisionShape2D):
                if node.size:
                    debug.draw_rect(
                        (
                            node.global_position[0],
                            node.global_position[1],
                            node.size[0],
                            node.size[1],
                        ),
                        color=self.settings.editor_settings["default_collision_color"],
                        space="world"
                    )

            highlight_axis = self._gizmo_drag_axis if self._gizmo_drag_active else self._gizmo_hover_axis
            debug.draw_gizmo(
                node.global_position,
                highlight_axis=highlight_axis,
                spacing_scale=self._get_gizmo_spacing_scale(),
            )

        



    def _collect_nodes(self, node, out=None):
        if out is None:
            out = []

        out.append(node)
        for child in getattr(node, "_children", []):
            self._collect_nodes(child, out)

        return out

    def run(self):
        last_frame_time = pygame.time.get_ticks()
        while pygui.is_dearpygui_running():
            now = pygame.time.get_ticks()
            delta = (now - last_frame_time) / 1000.0
            last_frame_time = now
            if not self.app.running:
                self.ui.check_resize()

            self._drain_commands()
            self._update_gizmo_cursor()
            self._update_gizmo_interaction()
            
            root = getattr(self.app.current_scene, "root", None)
            if root:
                self._update_node(root, delta)
            
            if self.app.current_scene:
                nodes_were_deleted = self.app.current_scene._process_deletion_queue()
                if nodes_were_deleted and hasattr(self, 'ui'):
                    self.ui._update_hierarchy()
            
            if not self.app.running:
                frame = self.render_frame()

            if not self.app.running:
                self.ui.push_frame(frame)
            pygui.render_dearpygui_frame()

        pygui.destroy_context()
    
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
        if new_width <= 0 or new_height <= 0: return False
            
        self.width, self.height = new_width, new_height
        
        self.app.internal_resolution = (self.width, self.height)
        self.settings.project_settings["window"]["internal_viewport_resolution"] = (self.width, self.height)

        new_surface = pygame.Surface((self.width, self.height)).convert_alpha()
        self.app.internal_surface = new_surface
        
        self.app.renderer.screen = new_surface
        
        return True

    def _update_node(self, node, delta):
        node.editor_update(delta)
        
        if getattr(node, "_queued_for_deletion", False):
            if self.app.current_scene and node not in self.app.current_scene.deletion_queue:
                self.app.current_scene.deletion_queue.append(node)

        for child in getattr(node, "_children", []):
            self._update_node(child, delta)
    

    def save_scene(self, scene=None, scene_path=None):
        if scene is None:
            scene = self.app.current_scene
        if scene_path is None:
            scene_path = getattr(scene, 'path', None) if scene else None
        
        try:
            ResourceServer.SceneLoader.save(scene, scene_path)

        except Exception as e:
            ErrorHandler.throw_error(f"Failed to save scene to {scene_path}, {e}")
        
    def load_scene(self, scene_path):
        if scene_path is None:
            ErrorHandler.throw_error(f"Failed to load scene from None")
        
        try:
            new_scene = ResourceServer.SceneLoader.load(scene_path)
            self.app.set_scene(new_scene)
            self.ui.state.selected_node = None
            self.ui.inspector.clear()
            self.ui._update_hierarchy()
            self.ui.menubar.update()
        
        except Exception as e: 
            ErrorHandler.throw_error(f"Error occured loading scene: {scene_path}, {e}")
        


    def run_scene(self, scene_path=None):
        #this needs to run in a subprocess to avoid freezing the editor
        try:
            if scene_path is None:
                scene_path = getattr(self.app.current_scene, 'path', None)
    
            if scene_path is None:
                ErrorHandler.throw_error("No scene path available to run")
                return

            scene_path = os.path.abspath(scene_path)
            if not ResourceServer.SceneLoader.save(self.app.current_scene, scene_path):
                ErrorHandler.throw_error(f"Failed to save scene before running: {scene_path}")
                return
            
            ErrorHandler.throw_info(f"Starting scene: {scene_path}...")
            import subprocess
            editor_file = os.path.abspath(__file__)
            src_root = os.path.dirname(os.path.dirname(os.path.dirname(editor_file)))

            env = os.environ.copy()
            if "SDL_VIDEODRIVER" in env:
                del env["SDL_VIDEODRIVER"]

            subprocess.run(
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
            ErrorHandler.throw_success("Scene finished running")
            
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to run scene: {e}")

    def drag_file(self):
        pass

class UIState:
    def __init__(self):
        self.selected_node = None
        self.selectables = {}

class EditorUI:
    def __init__(self, _editor: KodEditor, _app):
        self.editor = _editor
        self.app = _app
        self.state = UIState()
        self.viewport = UIComp.ViewportPanel(self)
        self.hierarchy = UIComp.HierarchyPanel(self)
        self.inspector = UIComp.InspectorPanel(self)
        self.console = UIComp.ConsolePanel(self)
        self.dialogs = UIComp.NodeDialogs(self)
        self.menubar = UIComp.MenuBar(self)
        self.file_system = UIComp.FileSystem(self)
        

        pygui.create_context()
        self.viewport.create_texture()
        self._create_layout()
        self._setup_dpg()

        ErrorHandler.set_console_callback(self._handle_console_message)

        if pygui.does_item_exist("add_node_btn"):
            pygui.configure_item("add_node_btn", enabled=False)

    def _create_layout(self):
        with pygui.window(tag="Primary Window"):
            with pygui.table(header_row=False, resizable=False, borders_innerV=False, height=20):
                pygui.add_table_column(init_width_or_weight=0.2)
                pygui.add_table_column(init_width_or_weight=0.6)
                pygui.add_table_column(init_width_or_weight=0.2)

                with pygui.table_row():
                    self.menubar.build()

            with pygui.table(header_row=False, resizable=True, borders_innerV=True):
                pygui.add_table_column(init_width_or_weight=0.2)
                pygui.add_table_column(init_width_or_weight=0.6)
                pygui.add_table_column(init_width_or_weight=0.2)

                with pygui.table_row():
                    with pygui.child_window(border=True):
                        self.hierarchy.build()

                    with pygui.group():

                        with pygui.child_window(tag="viewport_container", border=True, height=-250, no_scrollbar=True):
                            pygui.add_text("Engine Viewport", color=(150, 150, 150))
                            pygui.add_image("engine_texture", tag="viewport_image")

                        with pygui.child_window(border=True, height=-1):
                            with pygui.tab_bar(tag="bottom_dock_tabs"):
                                with pygui.tab(label="Console"):
                                    self.console.build()
                                
                                with pygui.tab(label="File System"):
                                    pygui.add_text("File System", color=(150, 150, 150))
                                    pygui.add_separator()
                                    with pygui.child_window(border=False, tag="file_system_tree"):
                                        self.file_system.build()
                                    
                                    with pygui.handler_registry():
                                        pygui.add_mouse_click_handler(button=pygui.mvMouseButton_Right, callback=self._file_system_right_click)

                    with pygui.child_window(border=True, tag="inspector_panel"):
                        self.inspector.build()

    def _setup_dpg(self):
        pygui.create_viewport(title="KodEngine Editor", width=1400, height=900)
        pygui.setup_dearpygui()
        pygui.show_viewport()
        pygui.set_primary_window("Primary Window", True)

        with pygui.handler_registry():
            pygui.add_mouse_wheel_handler(callback=self._on_mouse_wheel)

    def check_resize(self):
        self.viewport.check_resize()

    def push_frame(self, frame):
        self.viewport.push_frame(frame)

    def _update_hierarchy(self):
        self.hierarchy.update_hierarchy()

    def _clear_inspector(self):
        self.inspector.clear()
    
    def _file_system_right_click(self, sender, app_data):
        if pygui.is_item_hovered("file_system_tree"):
            self.file_system._show_context_menu()
    
    # TODO: Implement file opening logic
    def _open_file(self, file_path):
        pass
    
    def _handle_console_message(self, msg_type: str, message: str):
        if hasattr(self, 'console'):
            self.console.add_message(msg_type, message)

    def _on_mouse_wheel(self, sender, app_data):
        self.editor.on_mouse_wheel(app_data)
    


def main():
    editor = KodEditor()
    editor.run()

if __name__ == "__main__":
    main()
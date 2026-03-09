#GENERAL IMPORTY
import dearpygui.dearpygui as pygui
import numpy as np
import pygame
import os
import sys

#i need to run this in a dummy environment to eliminate event overlaps between dpg and pygame
os.environ["SDL_VIDEODRIVER"] = "dummy"

#EDITOR IMPORTS
from . import ui_components as UIComp

#ENGINE IMPORTS
from ..engine import Kod, Nodes, ResourceServer
from ..engine.ErrorHandler import ErrorHandler

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

        scene_path = os.path.join(project_dir, "scenes", "world.kscn")
        loaded_scene = ResourceServer.SceneLoader.load(scene_path)

        self.camera = Nodes.Camera2D()
        
        self.app.set_camera(self.camera)
        self.app.set_scene(loaded_scene)

        self.width, self.height = self.initial_res
        self.ui = EditorUI(self, self.app)
    
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
        debug.clear_command_list()

        root = getattr(self.app.current_scene, "root", None)
        if root is None:
            return

        for node in self._collect_nodes(root):
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

                    debug.draw_gizmo(node.global_position)

        



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
    


def main():
    editor = KodEditor()
    editor.run()

if __name__ == "__main__":
    main()
#GENERAL IMPORTY
import dearpygui.dearpygui as pygui
import numpy as np
import pygame
import os
import subprocess
import sys
import tempfile

#EDITOR IMPORTS
from . import ui_components as UIComp

#ENGINE IMPORTS
from ..engine import Kod, Nodes, Scenes, Scripts, NodeComponents, ResourceManager
from ..engine.ErrorHandler import ErrorHandler

#SCRIPTS TODO: musim predelat protoze to je uplne na picu

class KodEditor:
    def __init__(self):
        ErrorHandler.set_editor_mode(True)
        self.settings = Kod.Settings()
        self.initial_res = (640, 360)
        self.settings.window_settings["internal_viewport_resolution"] = self.initial_res
        self.app = Kod.App(self.settings, editor_mode=True)

        current_scene = ResourceManager.SceneLoader.load("src/BeatSlash/scenes/world.kscn")
        self.current_scene_path = getattr(current_scene, 'path', None)

        self.camera = Nodes.Camera2D()
        
        self.root = getattr(current_scene, "root", None)
        if self.root is None:
            self.root = Nodes.Node2D()
        
        self.app.set_camera(self.camera)
        self.app.set_scene(current_scene)

        self.width, self.height = self.initial_res
        self.ui = EditorUI(self, self.app)

    def render_frame(self):
        if not self.app.screen:
            ErrorHandler.throw_error("No screen supplied. Stopping rendering")
            return None

        self.app.renderer.render_frame(self.app.current_scene, self.camera)
        self.app.scaled_surface = pygame.transform.scale(self.app.internal_surface, self.app.resolution)
        self.app.screen.blit(self.app.scaled_surface, (0, 0))

        self.app.clock.tick(self.app.FPS)
        
        data = pygame.surfarray.array3d(self.app.internal_surface)
        data = data.transpose([1, 0, 2])
        alpha = np.full((self.height, self.width, 1), 255, dtype=np.uint8)
        rgba = np.concatenate((data, alpha), axis=2)
        return rgba.astype(np.float32) / 255.0

    def run(self):
        last_frame_time = pygame.time.get_ticks()
        while pygui.is_dearpygui_running():
            now = pygame.time.get_ticks()
            delta = (now - last_frame_time) / 1000.0
            last_frame_time = now
            if not self.app.running:
                self.ui.check_resize()
            
            self._update_node(self.root, delta)
            
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
        def build(node):
            return {child: build(child) for child in getattr(node, "_children", [])}
        return {self.root: build(self.root)}


    def update_viewport_size(self, new_width, new_height):
        new_width, new_height = int(new_width), int(new_height)
        if new_width == self.width and new_height == self.height:
            return False
        if new_width <= 0 or new_height <= 0: return False
            
        self.width, self.height = new_width, new_height
        
        self.app.internal_resolution = (self.width, self.height)
        self.settings.window_settings["internal_viewport_resolution"] = (self.width, self.height)

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
    

    def _save_scene(self, scene=None, scene_path=None):
        if scene is None:
            scene = self.app.current_scene
        if scene_path is None:
            scene_path = getattr(scene, 'path', self.current_scene_path) if scene else self.current_scene_path
    
        if ResourceManager.SceneLoader.save(scene, scene_path):
            self.current_scene_path = scene_path
            ErrorHandler.throw_success(f"Scene saved to {scene_path}!")
        else:
            ErrorHandler.throw_error(f"Failed to save scene to {scene_path}")

    def _load_scene(self, scene_path=None):
        if scene_path is None:
            scene_path = self.current_scene_path
        result = ResourceManager.SceneLoader.load(scene_path)
        if result:
            self.app.set_scene(result)
            self.current_scene_path = getattr(result, 'path', scene_path)
            ErrorHandler.throw_success(f"Scene loaded from {scene_path}!")
            self.ui._update_hierarchy()
        else:
            ErrorHandler.throw_error(f"Failed to load scene from {scene_path}")

    def _run_scene(self, scene_path=None):
        #this needs to run in a subprocess to avoid freezing the editor
        try:
            if scene_path is None:
                scene_path = getattr(self.app.current_scene, 'path', self.current_scene_path) if self.app.current_scene else self.current_scene_path
    
            if scene_path is None:
                ErrorHandler.throw_error("No scene path available to run")
                return

            scene_path = os.path.abspath(scene_path)
            if not ResourceManager.SceneLoader.save(self.app.current_scene, scene_path):
                ErrorHandler.throw_error(f"Failed to save scene before running: {scene_path}")
                return
            
            ErrorHandler.throw_info(f"Starting scene: {scene_path}...")
            import subprocess
            editor_file = os.path.abspath(__file__)
            src_root = os.path.dirname(os.path.dirname(os.path.dirname(editor_file)))

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "KodEngine.editor.subprocess.runtime",
                    "--scene",
                    scene_path,
                ],
                cwd=src_root,
            )
            ErrorHandler.throw_success("Scene finished running")
            
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to run scene: {e}")

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
                            self.console.build()

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
    
    def _handle_console_message(self, msg_type: str, message: str):
        if hasattr(self, 'console'):
            self.console.add_message(msg_type, message)
    


def main():
    editor = KodEditor()
    editor.run()

if __name__ == "__main__":
    main()
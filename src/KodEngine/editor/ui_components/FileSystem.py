import dearpygui.dearpygui as pygui
from ...engine import ErrorHandler
import os
import time

from ...engine import ResourceManager, Nodes, Scenes

ignored_file_list = ["__init__.py"]
ignored_directory_list = ["__pycache__"]

class FileSystem:
    def __init__(self, ui) -> None:
        self.ui = ui
        self._last_click_time = {}
        self._double_click_threshold = 0.5
        self._context_menu_path = None
        self._selected_directory = None
        self._open_directories = set()  # Track which directories are open
    
    def build(self, path=None):
        if path is None:
            path = self.ui.app.configuration.project_settings["file_management"]["project_directory"]

        item = path.split("/")[-1]
        with pygui.tree_node(label=f"{item}", default_open=False):
            self._build_file_tree(path)
        
        if not pygui.does_item_exist("file_system_context_menu"):
            self._create_context_menu()

    #recursive building of file tree
    def _build_file_tree(self, path=None):
        if path is None:
            path = self.ui.app.configuration.project_settings["file_management"]["project_directory"]
        
        try:
            items = sorted(os.listdir(path))
            for item in items:
                if item.startswith('.') or (item in ignored_file_list) or (item in ignored_directory_list):
                    continue

                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    # Use stable path-based tags instead of id()
                    tree_tag = f"dir_item_{full_path.replace('/', '_').replace(' ', '_')}"
                    selectable_tag = f"dir_selectable_{full_path.replace('/', '_').replace(' ', '_')}"
                    
                    # Check if this directory was previously open
                    was_open = full_path in self._open_directories
                    
                    pygui.add_selectable(
                        label=f"{item}",
                        user_data=full_path,
                        tag=selectable_tag,
                        callback=self._on_directory_select,
                        drop_callback=self._on_file_drop_on_directory,
                        payload_type="file_payload",
                        span_columns=True
                    )
                    with pygui.tree_node(label=f"{item}", default_open=was_open, tag=tree_tag, user_data=full_path, indent=20):
                        self._build_file_tree(full_path)
                else:

                    selectable_tag = f"file_item_{full_path.replace('/', '_').replace(' ', '_')}"
                    pygui.add_selectable(
                        label=f"{item}", 
                        user_data=full_path, 
                        tag=selectable_tag, 
                        drag_callback=self.ui.editor.drag_file,
                        callback=self._on_file_double_click
                    )
                    with pygui.drag_payload(parent=selectable_tag, drag_data=full_path, payload_type="file_payload"):
                        pygui.add_text(f"{item}")

        except Exception as e:
            ErrorHandler.throw_error(f"Failed to load file tree: {e}")
    
    def _on_file_double_click(self, sender, app_data, user_data):
        file_path : str = user_data
        if file_path is None:
            return
        
        current_time = time.time()
        # Use file path as key instead of sender which changes on rebuild
        last_time = self._last_click_time.get(file_path, 0)
        time_diff = current_time - last_time
        
        self._last_click_time[file_path] = current_time
        
        if time_diff < self._double_click_threshold:
            if file_path.endswith(".kscn"):
                self.ui.editor.load_scene(file_path)
    
    def _on_directory_select(self, sender, app_data, user_data):
        directory_path = user_data
        self._selected_directory = directory_path
        ErrorHandler.throw_info(f"Selected directory: {os.path.basename(directory_path)}")
    
    def _on_file_drop_on_directory(self, sender, app_data, user_data):
        try:
            source_path = app_data
            if source_path is None or not isinstance(source_path, str):
                ErrorHandler.throw_error("No valid file path in drop event")
                return
            
            target_dir = pygui.get_item_user_data(sender)
            if target_dir is None or not os.path.isdir(target_dir):
                ErrorHandler.throw_error("Invalid target directory")
                return
            
            source_dir = os.path.dirname(source_path)
            if source_dir == target_dir:
                ErrorHandler.throw_info("File is already in this directory")
                return
            
            filename = os.path.basename(source_path)
            dest_path = os.path.join(target_dir, filename)
            
            if os.path.exists(dest_path):
                ErrorHandler.throw_error(f"File '{filename}' already exists in target directory")
                return

            import shutil
            shutil.move(source_path, dest_path)
            
            ErrorHandler.throw_success(f"Moved '{filename}' to '{os.path.basename(target_dir)}'")
            self._refresh_file_tree()
            
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to move file: {e}")
    
    def _create_context_menu(self):
        with pygui.window(label="FileSystem Context Menu", tag="file_system_context_menu", show=False, no_title_bar=True, popup=True):
            pygui.add_menu_item(label="New Script", callback=self._create_new_script)
            pygui.add_menu_item(label="New Scene", callback=self._create_new_scene)
            pygui.add_separator()
            pygui.add_menu_item(label="Refresh", callback=self._refresh_file_tree)
    
    def _show_context_menu(self, path=None):
        if self._selected_directory:
            self._context_menu_path = self._selected_directory
        elif path:
            self._context_menu_path = path
        else:
            self._context_menu_path = self.ui.app.configuration.project_settings["file_management"]["project_directory"]
        
        mouse_pos = pygui.get_mouse_pos(local=False)
        pygui.configure_item("file_system_context_menu", show=True, pos=mouse_pos)
    
    def _refresh_file_tree(self):
        pygui.configure_item("file_system_context_menu", show=False)
        self._capture_open_directories()
        pygui.delete_item("file_system_tree", children_only=True)
        with pygui.child_window(parent="file_system_tree", border=False):
            self.build()
        ErrorHandler.throw_info("File tree refreshed")

    def _capture_open_directories(self):
        """Capture current open/closed state of directory nodes before rebuild."""
        self._open_directories.clear()
        root_path = self.ui.app.configuration.project_settings["file_management"]["project_directory"]

        for dirpath, dirnames, _ in os.walk(root_path):
            for dirname in dirnames:
                full_path = os.path.join(dirpath, dirname)
                tree_tag = f"dir_item_{full_path.replace('/', '_').replace(' ', '_')}"
                if pygui.does_item_exist(tree_tag):
                    try:
                        state = pygui.get_item_state(tree_tag)
                        if state and state.get("open"):
                            self._open_directories.add(full_path)
                    except Exception:
                        continue
    
    def _create_new_script(self):
        pygui.configure_item("file_system_context_menu", show=False)
        
        if pygui.does_item_exist("new_script_window"):
            pygui.delete_item("new_script_window")
        
        modal_width = 400
        modal_height = 150
        
        with pygui.window(label="New Script", tag="new_script_window", modal=True, show=True, width=modal_width, height=modal_height):
            pygui.add_text("Enter script name:")
            pygui.add_input_text(tag="new_script_name_input", default_value="new_script.py", width=-1)
            pygui.add_separator()
            with pygui.group(horizontal=True):
                pygui.add_button(label="Create", width=190, callback=self._on_create_script_confirm)
                pygui.add_button(label="Cancel", width=190, callback=lambda: pygui.delete_item("new_script_window"))
        
        main_width = pygui.get_item_width("Primary Window") or 1280
        main_height = pygui.get_item_height("Primary Window") or 720
        modal_x = int((main_width / 2 - modal_width / 2))
        modal_y = int((main_height / 2 - modal_height / 2))
        pygui.set_item_pos("new_script_window", [modal_x, modal_y])
    
    def _on_create_script_confirm(self):
        script_name = pygui.get_value("new_script_name_input")
        
        if not script_name:
            ErrorHandler.throw_error("Script name cannot be empty")
            return
        
        if not script_name.endswith(".py"):
            script_name += ".py"
        
        target_dir = self._context_menu_path
        if target_dir is None:
            target_dir = self.ui.app.configuration.project_settings["file_management"]["project_directory"]
        
        if not os.path.isdir(target_dir):
            target_dir = os.path.dirname(target_dir)
        
        script_path = os.path.join(target_dir, script_name)
        
        if os.path.exists(script_path):
            ErrorHandler.throw_error(f"File already exists: {script_name}")
            return
        
        try:
            template = """# Script Template 
        
def _ready(self):
    pass # Called on child addded to scene tree

def _process(self, delta):
    pass # Called every frame

def _input(self, events):
    pass # Grab inputs from pygame

"""
            with open(script_path, 'w') as f:
                f.write(template)
            
            ErrorHandler.throw_success(f"Created script: {script_name}")
            self._refresh_file_tree()
            pygui.delete_item("new_script_window")
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to create script: {e}")
    
    def _create_new_scene(self):
        pygui.configure_item("file_system_context_menu", show=False)
        
        if pygui.does_item_exist("new_scene_window"):
            pygui.delete_item("new_scene_window")
        
        modal_width = 400
        modal_height = 150
        
        with pygui.window(label="New Scene", tag="new_scene_window", modal=True, show=True, width=modal_width, height=modal_height):
            pygui.add_text("Enter scene name:")
            pygui.add_input_text(tag="new_scene_name_input", default_value="new_scene.kscn", width=-1)
            pygui.add_separator()
            with pygui.group(horizontal=True):
                pygui.add_button(label="Create", width=190, callback=self._on_create_scene_confirm)
                pygui.add_button(label="Cancel", width=190, callback=lambda: pygui.delete_item("new_scene_window"))
        
        main_width = pygui.get_item_width("Primary Window") or 1400
        main_height = pygui.get_item_height("Primary Window") or 900
        modal_x = int((main_width / 2 - modal_width / 2))
        modal_y = int((main_height / 2 - modal_height / 2))
        pygui.set_item_pos("new_scene_window", [modal_x, modal_y])
    
    def _on_create_scene_confirm(self):
        
        scene_name = pygui.get_value("new_scene_name_input")
        
        if not scene_name:
            ErrorHandler.throw_error("Scene name cannot be empty")
            return
        
        if not scene_name.endswith(".kscn"):
            scene_name += ".kscn"
        
        target_dir = self._context_menu_path
        if target_dir is None:
            target_dir = self.ui.app.configuration.project_settings["file_management"]["project_directory"]
        
        if not os.path.isdir(target_dir):
            target_dir = os.path.dirname(target_dir)
        
        scene_path = os.path.join(target_dir, scene_name)
        
        if os.path.exists(scene_path):
            ErrorHandler.throw_error(f"File already exists: {scene_name}")
            return
        
        try:
            root_node = Nodes.Node2D()
            root_node.name = "Root"
            new_scene = Scenes.Scene(name=scene_name, root=root_node)
            
            if ResourceManager.SceneLoader.save(new_scene, scene_path):
                ErrorHandler.throw_success(f"Created scene: {scene_name}")
                self._refresh_file_tree()
                pygui.delete_item("new_scene_window")
            else:
                ErrorHandler.throw_error(f"Failed to save scene: {scene_name}")
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to create scene: {e}")
            
import dearpygui.dearpygui as pygui

class MenuBar:
    def __init__(self, ui) -> None:
        self.ui = ui

    def build(self):
        with pygui.child_window(border=False, height=20, menubar=True, no_scrollbar=True):
            with pygui.menu_bar():
                with pygui.menu(label="File"):
                    pygui.add_menu_item(label="Save Scene", callback=lambda: self.ui.editor._save_scene())
                    pygui.add_menu_item(label="Load Scene", callback=lambda: self.ui.editor._load_scene())

        scene_name_text = ""
        current_scene_name = self.ui.app.current_scene.name
        scene_path = getattr(self.ui.app.current_scene, 'path', "")
        if current_scene_name:
            scene_name_text = str(current_scene_name).replace("_", " ").title()
        
        pygui.add_text(f"{scene_name_text} ({scene_path})")

        with pygui.child_window(border=False, height=20, no_scrollbar=True):
            pygui.add_button(label="Run Scene", width=-1, callback=lambda: self.ui.editor._run_scene())

    

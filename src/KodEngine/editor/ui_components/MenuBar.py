import dearpygui.dearpygui as pygui
from ..EditorModels import EditorCommandType

class MenuBar:
    def __init__(self, ui) -> None:
        self.ui = ui

    def _get_scene_display_text(self):
        scene_name = self.ui.app.current_scene.name or ""
        scene_path = getattr(self.ui.app.current_scene, 'path', "")
        
        scene_name_text = str(scene_name).replace("_", " ").title() if scene_name else ""
        scene_path_text = self.ui.editor.to_relative_path(scene_path) if scene_path else ""
        
        return f"{scene_name_text} ({scene_path_text})"

    def _build_menu_bar(self):
        with pygui.child_window(border=False, height=20, menubar=True, no_scrollbar=True):
            with pygui.menu_bar():
                with pygui.menu(label="File"):
                    pygui.add_menu_item(label="Save Scene", callback=lambda: self.ui.editor.queue_command(EditorCommandType.SAVE_SCENE))
                with pygui.menu(label="Edit"):
                    pygui.add_menu_item(label="Editor Settings", callback=lambda: self.ui.editor.queue_command(EditorCommandType.OPEN_EDITOR_SETTINGS))

    def _build_scene_info(self):
        display_text = self._get_scene_display_text()
        pygui.add_text(display_text, tag="menubar_scene_info")

    def _build_action_buttons(self):
        with pygui.child_window(border=False, height=20, no_scrollbar=True):
            pygui.add_button(label="Run Project", width=-1, callback=lambda: self.ui.editor.queue_command(EditorCommandType.RUN_PROJECT))
        with pygui.child_window(border=False, height=20, no_scrollbar=True):
            pygui.add_button(label="Run Scene",width=-1,callback=lambda: self.ui.editor.queue_command(EditorCommandType.RUN_SCENE, scene_path=str(self.ui.editor.app.current_scene.path)))

    def build(self):
        self._build_menu_bar()
        self._build_scene_info()
        self._build_action_buttons()

    def clear(self):
        if pygui.does_item_exist("menubar_scene_info"):
            pygui.delete_item("menubar_scene_info")

    def update(self):
        display_text = self._get_scene_display_text()
        
        if pygui.does_item_exist("menubar_scene_info"):
            pygui.configure_item("menubar_scene_info", default_value=display_text)
        else:
            self._build_scene_info()

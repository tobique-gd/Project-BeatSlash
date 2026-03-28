import dearpygui.dearpygui as pygui

from . import ui_components as UIComp
from .EditorModels import EditorSessionState
from ..engine.ErrorHandler import ErrorHandler


class EditorUI:
    def __init__(self, editor, app):
        self.editor = editor
        self.app = app
        self.state = EditorSessionState()
        self.viewport = UIComp.ViewportPanel(self)
        self.hierarchy = UIComp.HierarchyPanel(self)
        self.inspector = UIComp.InspectorPanel(self)
        self.console = UIComp.ConsolePanel(self)
        self.dialogs = UIComp.Dialogs.DialogManager(self, self.editor.editor_settings)
        self.menubar = UIComp.MenuBar(self)
        self.file_system = UIComp.FileSystem(self)

        pygui.create_context()
        with pygui.font_registry():
            default_font = pygui.add_font("src/KodEngine/editor/assets/fonts/kod_default_font.otf", 16)
            pygui.bind_font(default_font)

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
                pygui.add_table_column(init_width_or_weight=0.1)
                pygui.add_table_column(init_width_or_weight=0.1)

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
                                        pygui.add_mouse_click_handler(
                                            button=pygui.mvMouseButton_Right,
                                            callback=self._file_system_right_click,
                                        )

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

    

    def _handle_console_message(self, msg_type: str, message: str):
        if hasattr(self, "console"):
            self.console.add_message(msg_type, message)

    def _on_mouse_wheel(self, sender, app_data):
        self.editor.on_mouse_wheel(app_data)

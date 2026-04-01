import dearpygui.dearpygui as pygui
from ...engine import Nodes
from ...engine.ErrorHandler import ErrorHandler
from ...engine import ResourceServer
from .. import ResourceEditors
import os

class BaseDialog:
    def __init__(self, ui):
        self.ui = ui

    def _show_centered_modal(self, *, label, tag, width, height, no_resize=False):
        if pygui.does_item_exist(tag):
            pygui.delete_item(tag)

        with pygui.window(
            label=label,
            tag=tag,
            modal=False,
            show=True,
            width=width,
            height=height,
            no_resize=no_resize,
            no_collapse=True,
        ):
            pass

        main_width = pygui.get_item_width("Primary Window") or 1400
        main_height = pygui.get_item_height("Primary Window") or 900
        modal_x = int((main_width / 2 - width / 2))
        modal_y = int((main_height / 2 - height / 2))
        pygui.set_item_pos(tag, [modal_x, modal_y])
        return tag


class NodeDialogs(BaseDialog):
    def __init__(self, ui):
        super().__init__(ui)

    def get_node_classes(self):
        node_classes = []
        for attr_name in dir(Nodes):
            attr = getattr(Nodes, attr_name)
            if isinstance(attr, type) and issubclass(attr, Nodes.Node) and attr is not Nodes.Node:
                node_classes.append((attr_name, attr))
        return sorted(node_classes, key=lambda x: x[0])

    def show_delete_node_window(self, sender, app_data):
        if not self.ui.state.selected_node:
            return

        self._show_centered_modal(
            label="Delete Node",
            tag="delete_node_window",
            width=300,
            height=80,
            no_resize=True,
        )

        with pygui.group(parent="delete_node_window"):
            pygui.add_text(f"Do you really want to delete '{self.ui.state.selected_node.name}'?")
            pygui.add_separator()
            with pygui.group(horizontal=True):
                pygui.add_button(label="Delete", width=140, callback=self.delete_selected_node)
                pygui.add_button(label="Cancel", width=140, callback=lambda: pygui.delete_item("delete_node_window"))

    def delete_selected_node(self, sender=None, app_data=None):
        if not self.ui.state.selected_node:
            return
        
        if self.ui.state.selected_node == self.ui.editor.app.current_scene.root:
            ErrorHandler.throw_warning("Cannot delete root node")
            if pygui.does_item_exist("delete_node_window"):
                pygui.delete_item("delete_node_window")
            return
        
        try:
            self.ui.state.selected_node.queue_free()
        except Exception as e:
            ErrorHandler.throw_error(f"Error deleting node: {e}")
        
        
        if pygui.does_item_exist("delete_node_window"):
            pygui.delete_item("delete_node_window")

        self.ui.state.selected_node = None
        self.ui._update_hierarchy()
        self.ui.inspector.update(None)


    def _draw_scene_file_browser(self):
        root = self.ui.editor.settings.project_settings["file_management"]["project_directory"]

        def draw_dir(path):
            try:
                entries = sorted(os.listdir(path))
            except Exception:
                ErrorHandler.throw_error(f"Error accessing directory: {path}")
                return

            for entry in entries:
                full_path = os.path.join(path, entry)

                if os.path.isdir(full_path):
                    with pygui.tree_node(label=entry, default_open=False):
                        draw_dir(full_path)
                else:
                    if not entry.endswith(".kscn"):
                        continue

                    pygui.add_selectable(
                        label=entry,
                        user_data=full_path,
                        callback=self._on_scene_file_selected,
                        default_value=(
                            self.ui.file_system.get_selected_file() == full_path
                        )
                    )

        draw_dir(root)

    def show_link_scene_window(self, sender, app_data):
        if not self.ui.state.selected_node:
            return

        self._show_centered_modal(
            label="Link Scene",
            tag="link_scene_window",
            width=640,
            height=400,
            no_resize=True,
        )

        with pygui.group(parent="link_scene_window"):
            pygui.add_text("Select a scene to link (.kscn):")
            pygui.add_separator()

            with pygui.child_window(
                tag="link_scene_file_browser",
                border=True,
                height=-60
            ):
                self._draw_scene_file_browser()

            pygui.add_separator()

            with pygui.group(horizontal=True):
                pygui.add_button(
                    label="Link",
                    width=300,
                    callback=self._on_scene_file_link_requested
                )
                pygui.add_button(
                    label="Cancel",
                    width=300,
                    callback=lambda: pygui.delete_item("link_scene_window")
                )
    def _on_scene_file_link_requested(self, sender, app_data, user_data):
        if not self.ui.state.selected_node:
            ErrorHandler.throw_warning("No node selected to link scene to")
            return
        
        selected_file = self.ui.file_system.get_selected_file()
        if not selected_file:
            ErrorHandler.throw_warning("No scene file selected")
            return
        
        try:
            pygui.delete_item("link_scene_window")
            linked_scene = ResourceServer.SceneLoader.load(selected_file)
            if not linked_scene:
                ErrorHandler.throw_error("Failed to load scene")
                return
            

            root = linked_scene.root
            if not root:
                ErrorHandler.throw_error("Linked scene has no root node")
                return
            root._is_linked_scene = True
            #TODO replace with proper relative path
            root._linked_scene_path = selected_file
            self.ui.state.selected_node.add_child(root)

            self.ui.hierarchy.update_hierarchy()
        except Exception as e:
            ErrorHandler.throw_error(f"Error linking scene: {e}")
   
    def _on_scene_file_selected(self, sender, app_data, user_data):
        self.ui.file_system.set_selected_file(user_data)

        parent = pygui.get_item_parent(sender)
        if not parent:
            return

        children = pygui.get_item_children(parent, 1) or []

        for child in children:
            if pygui.get_item_type(child) == "mvAppItemType::mvSelectable":
                pygui.set_value(child, child == sender)

    def show_add_node_window(self, sender, app_data):
        if not self.ui.state.selected_node:
            return

        modal_width = 300
        modal_height = 400

        self._show_centered_modal(
            label="Add Node",
            tag="add_node_window",
            width=modal_width,
            height=modal_height,
        )

        with pygui.group(parent="add_node_window"):
            pygui.add_text("Select a node type to add:")
            pygui.add_separator()

            node_classes = self.get_node_classes()

            for node_name, node_class in node_classes:
                pygui.add_button(
                    label=node_name,
                    width=-1,
                    user_data=node_class,
                    callback=self.on_node_type_selected
                )

    def on_node_type_selected(self, sender, app_data, user_data):
        if not self.ui.state.selected_node:
            ErrorHandler.throw_warning("No node selected to add child to")
            return

        node_class = user_data
        try:
            new_node = node_class()
            self.ui.state.selected_node.add_child(new_node)
            self.ui.hierarchy.update_hierarchy()
            ErrorHandler.throw_success(f"Created node '{node_class.__name__}' successfully")
            
            if pygui.does_item_exist("add_node_window"):
                pygui.delete_item("add_node_window")
        except Exception as e:
            ErrorHandler.throw_error(f"Error creating node: {e}")

    def show_change_type_window(self, sender, app_data):
        if not self.ui.state.selected_node:
            return

        modal_width = 300
        modal_height = 400
        current_type = type(self.ui.state.selected_node).__name__

        self._show_centered_modal(
            label="Change Node Type",
            tag="change_type_window",
            width=modal_width,
            height=modal_height,
        )

        with pygui.group(parent="change_type_window"):
            pygui.add_text(f"Current type: {current_type}")
            pygui.add_text("Select new type:")
            pygui.add_separator()

            node_classes = self.get_node_classes()

            for node_name, node_class in node_classes:
                pygui.add_button(
                    label=node_name,
                    width=-1,
                    user_data=node_class,
                    callback=self.on_change_type_selected
                )

    def on_change_type_selected(self, sender, app_data, user_data):
        if not self.ui.state.selected_node:
            ErrorHandler.throw_warning("No node selected")
            return

        old_node = self.ui.state.selected_node
        NewNodeClass = user_data
        current_type_name = type(old_node).__name__
        new_type_name = NewNodeClass.__name__
        
        if new_type_name == current_type_name:
            if pygui.does_item_exist("change_type_window"):
                pygui.delete_item("change_type_window")
            return
        
        try:
            new_node = NewNodeClass()
            
            
            for attr, value in vars(old_node).items():
               
                if attr.startswith("_") or attr in ("runtime_script",):
                    continue
                try:
                    setattr(new_node, attr, value)
                except Exception:
                    pass

          
            if old_node._parent:
                parent = old_node._parent
               
                idx = parent._children.index(old_node)
                parent._children[idx] = new_node
                new_node._parent = parent
            else:
               
                if self.ui.app.current_scene:
                    self.ui.app.current_scene.root = new_node
                    new_node._parent = None
                    
                    new_node.name = old_node.name 

           
            new_node._children = old_node._children
            for child in new_node._children:
                child._parent = new_node
            
           
            old_node._children = []
            old_node._parent = None

            self.ui.state.selected_node = new_node
            self.ui._update_hierarchy()
            self.ui.inspector.update(new_node)
            
            ErrorHandler.throw_success(f"Changed node type from {current_type_name} to {new_type_name}")
            
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to change node type: {e}")
        
        if pygui.does_item_exist("change_type_window"):
            pygui.delete_item("change_type_window")

class EditorSettingsDialog(BaseDialog):
    def __init__(self, ui, settings):
        super().__init__(ui)
        self.settings = settings
        self._selected_section = None

    def _format_setting_label(self, setting_key):
        return str(setting_key).replace("_", " ").title()

    def _set_setting_value(self, section_key, setting_key, value):
        try:
            section = self.settings.editor_settings.get(section_key, {})
            if not isinstance(section, dict):
                return

            section[setting_key] = value
            
        except Exception as e:
            ErrorHandler.throw_error(f"Error updating setting '{section_key}.{setting_key}': {e}")

    def _on_bool_changed(self, sender, app_data, user_data):
        section_key, setting_key = user_data
        self._set_setting_value(section_key, setting_key, bool(app_data))

    def _on_int_changed(self, sender, app_data, user_data):
        section_key, setting_key = user_data
        self._set_setting_value(section_key, setting_key, int(app_data))

    def _on_float_changed(self, sender, app_data, user_data):
        section_key, setting_key = user_data
        self._set_setting_value(section_key, setting_key, float(app_data))

    def _on_vec2_changed(self, sender, app_data, user_data):
        section_key, setting_key = user_data
        self._set_setting_value(section_key, setting_key, (float(app_data[0]), float(app_data[1])))

    def _on_color_changed(self, sender, app_data, user_data):
        section_key, setting_key = user_data
        self._set_setting_value(section_key, setting_key, (int(app_data[0]), int(app_data[1]), int(app_data[2])))

    def _on_text_changed(self, sender, app_data, user_data):
        section_key, setting_key = user_data
        self._set_setting_value(section_key, setting_key, app_data)

    def _draw_setting_widget(self, section_key, setting_key, setting_value):
        label = self._format_setting_label(setting_key)
        user_data = (section_key, setting_key)

        with pygui.table_row(parent=f"settings_table_{section_key}"):
            pygui.add_text(label)

            if isinstance(setting_value, bool):
                pygui.add_checkbox(
                    label=f"##setting_{section_key}_{setting_key}",
                    default_value=setting_value,
                    callback=self._on_bool_changed,
                    user_data=user_data,
                )
                return

            if isinstance(setting_value, int):
                pygui.add_drag_int(
                    label=f"##setting_{section_key}_{setting_key}",
                    default_value=setting_value,
                    width=-1,
                    callback=self._on_int_changed,
                    user_data=user_data,
                )
                return

            if isinstance(setting_value, float):
                pygui.add_drag_float(
                    label=f"##setting_{section_key}_{setting_key}",
                    default_value=setting_value,
                    width=-1,
                    callback=self._on_float_changed,
                    user_data=user_data,
                )
                return

            if isinstance(setting_value, (tuple, list)) and len(setting_value) == 2 and all(isinstance(v, (int, float)) for v in setting_value):
                pygui.add_drag_floatx(
                    label=f"##setting_{section_key}_{setting_key}",
                    default_value=[float(setting_value[0]), float(setting_value[1])],
                    size=2,
                    width=-1,
                    callback=self._on_vec2_changed,
                    user_data=user_data,
                )
                return

            if isinstance(setting_value, (tuple, list)) and len(setting_value) == 3 and all(isinstance(v, int) for v in setting_value):
                pygui.add_color_edit(
                    label=f"##setting_{section_key}_{setting_key}",
                    default_value=[int(setting_value[0]), int(setting_value[1]), int(setting_value[2])],
                    no_alpha=True,
                    width=-1,
                    callback=self._on_color_changed,
                    user_data=user_data,
                )
                return

            pygui.add_input_text(
                label=f"##setting_{section_key}_{setting_key}",
                default_value=str(setting_value),
                width=-1,
                on_enter=True,
                callback=self._on_text_changed,
                user_data=user_data,
            )

    def _draw_section_content(self, section_key):
        section_data = self.settings.editor_settings.get(section_key)
        if not isinstance(section_data, dict):
            pygui.add_text("Section data is invalid.", parent="editor_settings_content", color=(220, 100, 100))
            return

        header = self._format_setting_label(section_key)
        pygui.add_text(header, parent="editor_settings_content", color=(170, 170, 170))
        pygui.add_separator(parent="editor_settings_content")

        with pygui.table(parent="editor_settings_content", tag=f"settings_table_{section_key}", header_row=False, resizable=True):
            pygui.add_table_column(init_width_or_weight=0.42)
            pygui.add_table_column(init_width_or_weight=0.58)

            for setting_key, setting_value in section_data.items():
                self._draw_setting_widget(section_key, setting_key, setting_value)

    def _render_selected_section(self):
        if not pygui.does_item_exist("editor_settings_content"):
            return

        pygui.delete_item("editor_settings_content", children_only=True)

        if self._selected_section is None:
            pygui.add_text("No section selected.", parent="editor_settings_content", color=(170, 170, 170))
            return

        self._draw_section_content(self._selected_section)

    def _on_section_selected(self, sender, app_data, user_data):
        if not bool(app_data):
            pygui.set_value(sender, True)
            return

        if pygui.does_item_exist("editor_settings_sidebar"):
            sidebar_children = pygui.get_item_children("editor_settings_sidebar")
            if isinstance(sidebar_children, dict):
                selectable_children = sidebar_children.get(1) or []
            elif isinstance(sidebar_children, (list, tuple)):
                selectable_children = list(sidebar_children)
            else:
                selectable_children = []

            for child_tag in selectable_children:
                if child_tag is None or not pygui.does_item_exist(child_tag):
                    continue
                if pygui.get_item_type(child_tag) != "mvAppItemType::mvSelectable":
                    continue
                if child_tag != sender:
                    pygui.set_value(child_tag, False)

        self._selected_section = user_data
        self._render_selected_section()

    def _build_sections_sidebar(self):
        with pygui.child_window(tag="editor_settings_sidebar", width=-1, border=True):
            pygui.add_text("Sections", color=(170, 170, 170))
            pygui.add_separator()

            section_keys = list(self.settings.editor_settings.keys())
            for section_key in section_keys:
                pygui.add_selectable(
                    label=self._format_setting_label(section_key),
                    default_value=(section_key == self._selected_section),
                    user_data=section_key,
                    callback=self._on_section_selected,
                )

    def _build_section_content_panel(self):
        with pygui.child_window(tag="editor_settings_content", width=-1, border=True):
            pass

    def show_editor_settings_window(self, sender=None, app_data=None):
        modal_width = 800
        modal_height = 580

        self._show_centered_modal(
            label="Editor Settings",
            tag="editor_settings_window",
            width=modal_width,
            height=modal_height,
        )

        pygui.add_separator(parent="editor_settings_window")

        section_keys = list(self.settings.editor_settings.keys())
        self._selected_section = section_keys[0] if section_keys else None

        with pygui.table(parent="editor_settings_window", header_row=False, resizable=True, borders_innerV=True):
            pygui.add_table_column(init_width_or_weight=170)
            pygui.add_table_column(init_width_or_weight=530)

            with pygui.table_row():
                with pygui.table_cell():
                    self._build_sections_sidebar()
                with pygui.table_cell():
                    self._build_section_content_panel()

        self._render_selected_section()


class DialogManager:
    def __init__(self, ui, settings):
        self.ui = ui
        self.settings = settings
        self.node = NodeDialogs(ui)
        self.settings_dialog = EditorSettingsDialog(ui, settings)
        self._dialog_tags = (
            "add_node_window",
            "delete_node_window",
            "change_type_window",
            "editor_settings_window",
            "new_script_window",
            "new_scene_window",
            "link_scene_window",
        )

    def is_any_dialog_open(self):
        for tag in self._dialog_tags:
            if pygui.does_item_exist(tag) and pygui.is_item_shown(tag):
                return True
        return False

    def show_add_node_window(self, sender, app_data):
        self.node.show_add_node_window(sender, app_data)
    
    def show_link_scene_window(self, sender, app_data):
        self.ui.file_system.set_selected_file(None)
        self.node.show_link_scene_window(sender, app_data)

    def show_delete_node_window(self, sender, app_data):
        self.node.show_delete_node_window(sender, app_data)

    def show_change_type_window(self, sender, app_data):
        self.node.show_change_type_window(sender, app_data)

    def show_editor_settings_window(self, sender=None, app_data=None):
        self.settings_dialog.show_editor_settings_window(sender, app_data)


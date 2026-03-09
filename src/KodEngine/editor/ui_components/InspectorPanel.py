import dearpygui.dearpygui as pygui
import os
from ...engine import ErrorHandler
from ...engine import Nodes
from ...engine.Resources import *


class InspectorPanel:
    def __init__(self, ui):
        self.ui = ui

    def _resource_slot_info(self, node, attr, value):
        if isinstance(value, Resource):
            return True, value

        backing_candidates = [f"_{attr}_resource", f"_{attr}"]
        for backing_name in backing_candidates:
            if not hasattr(node, backing_name):
                continue

            backing_value = getattr(node, backing_name)
            if isinstance(backing_value, Resource):
                return True, backing_value
            if backing_value is None and isinstance(getattr(type(node), attr, None), property):
                return True, None

        return False, None

    def _resource_display_value(self, value):
        if value is None:
            return "None"

        path_value = None
        for field in ("resource_path", "texture_path", "file_path", "script_path"):
            candidate = getattr(value, field, None)
            if isinstance(candidate, str) and candidate:
                path_value = candidate
                break

        if path_value:
            display_value = self.ui.editor.to_relative_path(path_value)
        elif hasattr(value, "name") and getattr(value, "name"):
            display_value = str(value.name)
        else:
            display_value = str(value)

        if len(display_value) > 30:
            display_value = "..." + display_value[-27:]
        return display_value

    def _from_relative_path(self, path_str):
        if not isinstance(path_str, str) or not path_str:
            return path_str
            
        try:
            if os.path.isabs(path_str):
                return path_str
                
            project_directory = self.ui.editor.settings.project_settings["file_management"]["project_directory"]
            return os.path.abspath(os.path.join(project_directory, path_str))
        except Exception:
            return path_str

    def build(self):
        pygui.add_text("Inspector", color=(150, 150, 150))
        pygui.add_separator()

    def update(self, node):
        pygui.delete_item("inspector_panel", children_only=True)


        pygui.add_text("Inspector", parent="inspector_panel", color=(150, 150, 150))
        pygui.add_separator(parent="inspector_panel")

        with pygui.table(parent="inspector_panel", header_row=False, resizable=True):
            pygui.add_table_column(init_width_or_weight=0.35)
            pygui.add_table_column(init_width_or_weight=0.65)
            
            with pygui.table_row():
                pygui.add_text("Type")
                pygui.add_button(
                    label=type(node).__name__,
                    width=-1,
                    callback=self.ui.dialogs.show_change_type_window
                )

            self.draw_property(node, "name", getattr(node, "name", ""))

        excluded = {"_children", "_parent", "runtime_script", "name"}
        node_cls = type(node)
        mro = [cls for cls in node_cls.mro() if cls is not object]
        base_to_derived = list(reversed(mro))

        instance_items = []
        for attr, value in vars(node).items():
            if attr.startswith("_"):
                continue
            if attr in excluded:
                continue
            if callable(value):
                continue
            instance_items.append((attr, value))

        instance_order = {attr: index for index, (attr, _) in enumerate(instance_items)}

        instance_keys_by_class = {}
        for cls in base_to_derived:
            try:
                probe = cls()
                keys = {
                    key for key, value in vars(probe).items()
                    if not key.startswith("_") and key not in excluded and not callable(value)
                }
            except Exception:
                keys = set()
            instance_keys_by_class[cls] = keys

        introduced_by_class = {}
        cumulative = set()
        for cls in base_to_derived:
            keys = instance_keys_by_class.get(cls, set())
            introduced = keys - cumulative
            introduced_by_class[cls] = introduced
            cumulative |= keys

        property_owner = {}
        for cls in mro:
            for prop_name, descriptor in cls.__dict__.items():
                if not isinstance(descriptor, property):
                    continue
                if descriptor.fset is None:
                    continue
                if prop_name in excluded:
                    continue
                if prop_name not in property_owner:
                    property_owner[prop_name] = cls

        groups = {cls: [] for cls in mro}

        for attr, value in instance_items:
            owner = None
            for cls in base_to_derived:
                if attr in introduced_by_class.get(cls, set()):
                    owner = cls
            if owner is None:
                owner = node_cls
            groups.setdefault(owner, []).append((attr, value, instance_order.get(attr, 9999)))

        for prop_name, owner in property_owner.items():
            if any(existing_attr == prop_name for existing_attr, _ in instance_items):
                continue
            try:
                value = getattr(node, prop_name)
            except Exception:
                continue
            if callable(value):
                continue
            groups.setdefault(owner, []).append((prop_name, value, 10000 + len(groups.get(owner, []))))

        first_group = True
        for cls in mro:
            items = groups.get(cls, [])
            if not items:
                continue

            if not first_group:
                pygui.add_separator(parent="inspector_panel")
            first_group = False

            pygui.add_text(f"{cls.__name__}", parent="inspector_panel", color=(130, 130, 130))

            items = sorted(items, key=lambda item: item[2])
            with pygui.table(parent="inspector_panel", header_row=False, resizable=True):
                pygui.add_table_column(init_width_or_weight=0.35)
                pygui.add_table_column(init_width_or_weight=0.65)

                for attr, value, _ in items:
                    self.draw_property(node, attr, value)


    def draw_property(self, node, attr, value):
        FLOAT_MIN = -1000000.0
        FLOAT_MAX = 1000000.0
        INT_MIN = -1000000
        INT_MAX = 1000000
        label_text = attr.replace("_", " ").title()

        is_resource_slot, resource_value = self._resource_slot_info(node, attr, value)
        if is_resource_slot:
            with pygui.table_row():
                pygui.add_text(label_text)
                button_tag = f"resource_btn_{id(node)}_{attr}"
                display_value = self._resource_display_value(resource_value)
                
                pygui.add_button(
                    label=display_value,
                    tag=button_tag,
                    width=-1,
                    user_data=(node, attr),
                    drop_callback=self._drop_resource_file,
                    payload_type="file_payload"
                )
            return

        if isinstance(value, str):
            display_value = self.ui.editor.to_relative_path(value)

            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_input_text(
                    label=f"##{attr}",
                    default_value=display_value,
                    width=-1,
                    on_enter=True,
                    user_data=(node, attr),
                    drop_callback=self._drop_resource_file,
                    payload_type="file_payload",
                    callback=lambda s, a: setattr(
                        node,
                        attr,
                        self._from_relative_path(a)
                    ),
                )

            return

        if isinstance(value, bool):
            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_checkbox(
                    label=f"##{attr}",
                    default_value=value,
                    callback=lambda s, v: setattr(node, attr, v)
                )
            return

        if isinstance(value, int):
            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_drag_int(
                    label=f"##{attr}",
                    default_value=value,
                    min_value=INT_MIN,
                    max_value=INT_MAX,
                    width=-1,
                    callback=lambda s, v: setattr(node, attr, int(v))
                )
            return

        if isinstance(value, float):
            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_drag_float(
                    label=f"##{attr}",
                    default_value=value,
                    min_value=FLOAT_MIN,
                    max_value=FLOAT_MAX,
                    width=-1,
                    callback=lambda s, v: setattr(node, attr, float(v))
                )
            return

        if isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
            float_list = [float(value[0]), float(value[1])]
            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_drag_floatx(
                    label=f"##{attr}",
                    default_value=float_list,
                    size=2,
                    speed=0.1,
                    min_value=FLOAT_MIN,
                    max_value=FLOAT_MAX,
                    width=-1,
                    callback=lambda s, v: setattr(node, attr, (v[0], v[1]))
                )
            return

        with pygui.table_row():
            pygui.add_text(label_text)
            pygui.add_text(str(value))
            

    def _draw_collision_shape_editor(self, node, attr, value):
        from ...engine.Resources import CollisionRectangleShape
        # Add a resource path field to signify this can be a file
        resource_path = getattr(value, "resource_path", None)
        display_path = self.ui.editor.to_relative_path(resource_path) if resource_path else "<Local>"
        
        with pygui.table_row():
            pygui.add_text("Resource")
            pygui.add_button(
                label=display_path, 
                width=-1, 
                user_data=(node, attr),
                drop_callback=self._drop_resource_file
            )

        current_type = "RECTANGLE"
        
        with pygui.table_row():
            pygui.add_text("Shape Type")
            pygui.add_combo(
                items=["RECTANGLE"],
                default_value=current_type,
                width=-1,
                user_data=(node, attr),
                callback=self._on_shape_type_changed
            )

        if isinstance(value, CollisionRectangleShape):
            with pygui.table_row():
                pygui.add_text("Size")
                pygui.add_drag_floatx(
                    label="##size",
                    default_value=list(value.size),
                    size=2,
                    speed=1.0,
                    width=-1,
                    callback=lambda s, v: setattr(value, "size", tuple(v))
                )

    def _on_shape_type_changed(self, sender, new_type, user_data):
        node, attr = user_data
        try:
            if new_type == "RECTANGLE":
                new_shape = CollisionRectangleShape(size=(32, 32))
            setattr(node, attr, new_shape)
            ErrorHandler.throw_success(f"Changed shape to {new_type}")
            self.update(node)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to change shape: {e}")

    def clear(self):
        pygui.delete_item("inspector_panel", children_only=True)
        pygui.add_text("Inspector", parent="inspector_panel", color=(150, 150, 150))
        pygui.add_separator(parent="inspector_panel")

    def _drop_resource_file(self, sender, app_data, user_data):
        try:
            
            button_user_data = pygui.get_item_user_data(sender)
            if button_user_data is None:
                ErrorHandler.throw_error("No user data found on button")
                return
            
            node, attr = button_user_data
    
            file_path = app_data
            if file_path is None or not isinstance(file_path, str):
                ErrorHandler.throw_error("No valid file path in drop event")
                return
            
            try:
                
                setattr(node, attr, file_path)
                display_path = self.ui.editor.to_relative_path(file_path)
                ErrorHandler.throw_success(f"Set {attr} to: {display_path}")
                
                self.update(node)
            except Exception as e:
                ErrorHandler.throw_error(f"Failed to set {attr}: {e}")
                
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to process dropped file: {e}")

import dearpygui.dearpygui as pygui
import os
from ...engine import ErrorHandler
from ...engine import Nodes
from ...engine.Resources import CollisionRectangleShape, CollisionCircleShape

class InspectorPanel:
    def __init__(self, ui):
        self.ui = ui

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

        with pygui.table(parent="inspector_panel", header_row=False, resizable=True):
            pygui.add_table_column(init_width_or_weight=0.35)
            pygui.add_table_column(init_width_or_weight=0.65)

            for attr, value in vars(node).items():
                if attr.startswith("_"):
                    continue

                if attr in ("_children", "_parent", "runtime_script"):
                    continue

                if callable(value):
                    continue

                self.draw_property(node, attr, value)

            # Manually handle properties that are not in vars() (like @property styled attributes)
            # This is needed because 'texture' and 'audio' are now properties backed by private variables
            cls = type(node)
            for prop_name in dir(cls):
                 if prop_name in ("texture", "audio", "shape") and isinstance(getattr(cls, prop_name), property):
                     val = getattr(node, prop_name)
                     self.draw_property(node, prop_name, val)


    def draw_property(self, node, attr, value):
        FLOAT_MIN = -1000000.0
        FLOAT_MAX = 1000000.0

        if attr == "collision_shape":
            label_text = "Collision Shape"
            shape_display = "None"
            if value is not None:
                shape_display = getattr(value, 'name', str(value))
            
            with pygui.table_row():
                pygui.add_text(label_text)
                button_tag = f"collision_shape_btn_{id(node)}"
                pygui.add_button(
                    label=shape_display,
                    tag=button_tag,
                    width=-1,
                    user_data=(node, attr),
                    drop_callback=self._on_collision_shape_dropped,
                    payload_type="collision_shape_payload"
                )
            return


        if attr == "animations" and isinstance(value, (list, tuple)):
            label_text = "Animations"
            with pygui.table_row():
                pygui.add_text(label_text)
                with pygui.group():
                    for anim in value:
                        
                        try:
                            anim_name = anim["name"]
                        except Exception:
                            try:
                                anim_name = str(anim.name)
                            except Exception as e:
                                anim_name = "<unknown>"
                                ErrorHandler.throw_warning(f"Failed to resolve animation name: {e}")

                        pygui.add_button(label=anim_name,
                                         user_data=(node, anim_name),
                                         callback=lambda s, a, u: u[0].play(u[1]))
            return

        if attr == "current_animation":
            label_text = "Current Animation"
            name = None
            try:
                name = getattr(value, "name", None)
            except Exception:
                try:
                    name = value.get("name")
                except Exception:
                    name = None

            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_text(str(name))
            return

        if isinstance(value, str):
            label_text = attr.replace("_", " ").title()
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

        if attr == "shape" and isinstance(value, (CollisionRectangleShape, CollisionCircleShape)):
            self._draw_collision_shape_editor(node, attr, value)
            return

        # Explicitly handle CollisionShape resources if they aren't caught above 
        # (e.g. if I imported classes differently or type checking fails)
        if attr == "shape" and hasattr(value, "to_dict"): 
             # Fallback to generic resource button if custom editor not applicable
             pass 

        if isinstance(value, bool):
            label_text = attr.replace("_", " ").title()
            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_checkbox(label = f"##{attr}",
                                default_value=value,
                                callback=lambda s, v: setattr(node, attr, v)
                )
            return

        if hasattr(value, "__len__") and len(value) >= 2:
            try:
                float_list = [float(value[0]), float(value[1])]
                label_text = attr.replace("_", " ").title()
                with pygui.table_row():
                    pygui.add_text(label_text)
                    pygui.add_drag_floatx(
                        label = f"##{attr}",
                        default_value=float_list,
                        size=2,
                        speed=0.1,
                        min_value=FLOAT_MIN,
                        max_value=FLOAT_MAX,
                        width=-1,
                        callback=lambda s, v: setattr(node, attr, (v[0], v[1]))
                    )
                return
            except (TypeError, ValueError):
                ErrorHandler.throw_warning(
                    f"Attribute '{attr}' with value '{value}' could not be resolved as a 2D vector. Displaying as text instead."
                )
                label_text = attr.replace("_", " ").title()
                with pygui.table_row():
                    pygui.add_text(label_text)
                    pygui.add_text(str(value))
                
        try:
            val_as_float = float(value)
            label_text = attr.replace("_", " ").title()
            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_drag_float(label = f"##{attr}",
                                     default_value=val_as_float,
                                     min_value=FLOAT_MIN,
                                     max_value=FLOAT_MAX,
                                     width=-1,
                                     callback=lambda s, v: setattr(node, attr, v))
        except (TypeError, ValueError):
            label_text = attr.replace("_", " ").title()
            with pygui.table_row():
                pygui.add_text(label_text)
                button_tag = f"resource_btn_{id(node)}_{attr}"
                display_value = str(value) if value else "None"

                # Try to get a friendly name for resources
                if hasattr(value, "resource_path") and value.resource_path:
                    display_value = self.ui.editor.to_relative_path(value.resource_path)
                elif hasattr(value, "name"):
                    display_value = value.name

                if isinstance(value, str) and value:
                    display_value = self.ui.editor.to_relative_path(value)
                if len(display_value) > 30:
                    display_value = "..." + display_value[-27:]
                
                pygui.add_button(
                    label=display_value,
                    tag=button_tag,
                    width=-1,
                    user_data=(node, attr),
                    drop_callback=self._drop_resource_file,
                    payload_type="file_payload"
                )

    def _draw_collision_shape_editor(self, node, attr, value):
        from ...engine.Resources import CollisionRectangleShape, CollisionCircleShape

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
        if isinstance(value, CollisionCircleShape):
            current_type = "CIRCLE"
        
        with pygui.table_row():
            pygui.add_text("Shape Type")
            pygui.add_combo(
                items=["RECTANGLE", "CIRCLE", "POLYGON"],
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
        
        elif isinstance(value, CollisionCircleShape):
            with pygui.table_row():
                pygui.add_text("Radius")
                pygui.add_drag_float(
                    label="##radius",
                    default_value=value.radius,
                    speed=1.0,
                    width=-1,
                    callback=lambda s, v: setattr(value, "radius", v)
                )

    def _on_shape_type_changed(self, sender, new_type, user_data):
        node, attr = user_data
        try:
            if new_type == "RECTANGLE":
                new_shape = CollisionRectangleShape(size=(32, 32))
            elif new_type == "CIRCLE":
                new_shape = CollisionCircleShape(radius=16)
            
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

    def _on_collision_shape_dropped(self, sender, app_data, user_data):
        try:
            button_user_data = pygui.get_item_user_data(sender)
            if button_user_data is None:
                
                button_user_data = user_data
            
            if button_user_data is None:
                ErrorHandler.throw_error("No user data found on target button")
                return

            node, attr = button_user_data
            
            
            if isinstance(app_data, str) and app_data in self.ui.state.selectables:
                dropped_node = self.ui.state.selectables[app_data]
            else:
                dropped_node = app_data
            
            if not isinstance(dropped_node, Nodes.CollisionShape2D):
                ErrorHandler.throw_error("Can only drop CollisionShape2D nodes")
                return
            
            
            setattr(node, attr, dropped_node)
            self.update(node)
            ErrorHandler.throw_success(f"Assigned collision shape: {dropped_node.name}")
            
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to assign collision shape: {e}")

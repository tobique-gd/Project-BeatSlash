import dearpygui.dearpygui as pygui

class InspectorPanel:
    def __init__(self, ui):
        self.ui = ui

    def build(self):
        pygui.add_text("Inspector", color=(150, 150, 150))
        pygui.add_separator()

    def update(self, node):
        pygui.delete_item("inspector_panel", children_only=True)

        pygui.add_text("Inspector", parent="inspector_panel", color=(150, 150, 150))
        pygui.add_separator(parent="inspector_panel")

        pygui.add_text(f"Type: {type(node).__name__}", parent="inspector_panel")

        with pygui.table(parent="inspector_panel", header_row=False, resizable=True):
            pygui.add_table_column(init_width_or_weight=0.35)
            pygui.add_table_column(init_width_or_weight=0.65)

            for attr, value in vars(node).items():
                if attr.startswith("_"):
                    continue

                if attr in ("_children", "_parent", "script"):
                    continue

                if callable(value):
                    continue

                self.draw_property(node, attr, value)

    def draw_property(self, node, attr, value):
        FLOAT_MIN = -1000000.0
        FLOAT_MAX = 1000000.0

        
        if attr == "animations" and isinstance(value, (list, tuple)):
            label_text = "Animations"
            with pygui.table_row():
                pygui.add_text(label_text)
                with pygui.group():
                    for anim in value:
                        
                        try:
                            anim_name = anim["name"]
                        except Exception:
                            anim_name = str(anim.name)

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
            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_input_text(label = f"##{attr}",
                                    default_value=value,
                                    width=-1,
                                    callback=lambda s, v: setattr(node, attr, v)
                )
            return

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
                print("Error. Attribute (",attr,") or Value (",value,") could not be resolved. Displaying as text instead.")
                with pygui.table_row():
                    label_text = attr.replace("_", " ").title()
                    pygui.add_text(label_text)
                    pygui.add_text(value)
                
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
            print("Error. Attribute (",attr,") or Value (",value,") could not be resolved. Displaying as text instead.")

            with pygui.table_row():
                    label_text = attr.replace("_", " ").title()
                    pygui.add_text(label_text)
                    pygui.add_text(value)

    def clear(self):
        pygui.delete_item("inspector_panel", children_only=True)
        pygui.add_text("Inspector", parent="inspector_panel", color=(150, 150, 150))
        pygui.add_separator(parent="inspector_panel")

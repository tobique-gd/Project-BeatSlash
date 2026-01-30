import dearpygui.dearpygui as pygui
import pygame
import numpy as np
from KodEngine.engine import Kod, Nodes, Scenes, Scripts

class KodEditor:
    def __init__(self):
        self.settings = Kod.Settings()
        self.initial_res = (987, 760)
        self.settings.window_settings["internal_viewport_resolution"] = self.initial_res
        self.app = Kod.App(self.settings, editor_mode=True)

        self.sprite = Nodes.Sprite2D()
        self.sprite.texture = pygame.image.load("BeatSlash/assets/asd.png")
        self.root = Nodes.Node2D()
        self.root.name = "Epickej node"
        self.custom_node = Nodes.Node()
        self.custom_node.name = "custom nodeík"
        
        self.root.add_child(self.sprite)
        self.sprite.add_child(self.custom_node)

        class try_script(Scripts.Script):
            def __init__(self, node):
                super().__init__(node)

        self.sprite.script = try_script(self.sprite)

        self.scene = Scenes.Scene("World", self.root)
        self.camera = Nodes.Camera2D()

        self.app.set_camera(self.camera)
        self.app.set_scene(self.scene)

        self.width, self.height = self.initial_res
        self.ui = EditorUI(self)

    def render_frame(self):
        self.app.run_in_editor(self.camera)
        data = pygame.surfarray.array3d(self.app.internal_surface)
        data = data.transpose([1, 0, 2])
        alpha = np.full((self.height, self.width, 1), 255, dtype=np.uint8)
        rgba = np.concatenate((data, alpha), axis=2)
        return rgba.astype(np.float32) / 255.0

    def run(self):
        while pygui.is_dearpygui_running():
            self.ui.check_resize()
            
            frame = self.render_frame()
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

class EditorUI:
    def __init__(self, editor: KodEditor):
        self.selected_node = None
        self.selectables = {}

        self.editor = editor
        pygui.create_context()
        self._create_texture()
        self._create_layout()
        self._setup_dpg()

    def _create_texture(self):
        if pygui.does_alias_exist("engine_texture"):
            pygui.remove_alias("engine_texture")

        if pygui.does_item_exist("engine_texture"):
            pygui.delete_item("engine_texture")

        with pygui.texture_registry(show=False):
            initial_data = [0.0] * (self.editor.width * self.editor.height * 4)
            pygui.add_dynamic_texture(
                width=self.editor.width,
                height=self.editor.height,
                default_value=initial_data,
                tag="engine_texture"
            )

    def check_resize(self):
        if not pygui.does_item_exist("viewport_container"):
            return

        size = pygui.get_item_rect_size("viewport_container")
        new_w = max(int(size[0] - 10), 100)
        new_h = max(int(size[1] - 40), 100)

        if self.editor.update_viewport_size(new_w, new_h):
            self._create_texture()
            
            if pygui.does_item_exist("viewport_image"):
                pygui.configure_item("viewport_image", texture_tag="engine_texture")
                pygui.configure_item("viewport_image", width=new_w, height=new_h)

    def _create_layout(self):
        with pygui.window(tag="Primary Window"):
            with pygui.table(header_row=False, resizable=True, borders_innerV=True):
                pygui.add_table_column(init_width_or_weight=0.2)
                pygui.add_table_column(init_width_or_weight=0.6)
                pygui.add_table_column(init_width_or_weight=0.2)

                with pygui.table_row():

                    with pygui.child_window(border=True):
                        pygui.add_text("Hierarchy", color=(150, 150, 150))
                        pygui.add_separator()
                        self._draw_tree(self.editor.get_scene_hierarchy())


                    with pygui.group():

                        with pygui.child_window(tag="viewport_container", border=True, height=-250, no_scrollbar=True):
                            pygui.add_text("Engine Viewport", color=(150, 150, 150))
                            pygui.add_image("engine_texture", tag="viewport_image")

                        with pygui.child_window(border=True, height=-1):
                            pygui.add_text("Console", color=(150, 150, 150))
                            pygui.add_separator()
                            pygui.add_text("[Log]: Manual Resize check active.", color=(0, 255, 0))

                    with pygui.child_window(border=True, tag="inspector_panel"):
                        pygui.add_text("Inspector", color=(150, 150, 150))
                        pygui.add_separator()


    def _draw_tree(self, tree):
        for node, _children in tree.items():
            if _children:
                with pygui.tree_node(label=node.name, default_open=True):
                    self._add_node_selectable(node)
                    self._draw_tree(_children)
            else:
                self._add_node_selectable(node)

    def _add_node_selectable(self, node):
        tag = f"select_{id(node)}"

        self.selectables[tag] = node

        pygui.add_selectable(
            label=node.name,
            tag=tag,
            callback=self._on_node_selected
        )

    def _on_node_selected(self, sender, app_data):
        node = self.selectables[sender]

        for tag in self.selectables:
            pygui.set_value(tag, False)

        pygui.set_value(sender, True)

        self.selected_node = node
        self._update_inspector(node)

    def _update_inspector(self, node):
        pygui.delete_item("inspector_panel", children_only=True)

        pygui.add_text("Inspector", parent="inspector_panel", color=(150, 150, 150))
        pygui.add_separator(parent="inspector_panel")

        pygui.add_text(f"Type: {type(node).__name__}", parent="inspector_panel")

        for attr, value in vars(node).items():

            if attr.startswith("_"):
                continue

            if attr in ("_children", "_parent", "script"):
                continue

            if callable(value):
                continue

            self._draw_property(node, attr, value)

    def _draw_property(self, node, attr, value):
        FLOAT_MIN = -1000000.0
        FLOAT_MAX = 1000000.0

        parent = "inspector_panel"

        if isinstance(value, str):
            pygui.add_input_text(label = attr.replace("_", " ").title(),
                                 default_value=value, parent=parent,
                                 callback=lambda s, v: setattr(node, attr, v)
            )
            return

        if isinstance(value, bool):
            pygui.add_checkbox(label = attr.replace("_", " ").title(),
                               default_value=value, parent=parent,
                               callback=lambda s, v: setattr(node, attr, v)
            )
            return

        if hasattr(value, "__len__") and len(value) >= 2:
            try:
                float_list = [float(value[0]), float(value[1])]
                
                pygui.add_drag_floatx(
                    label = attr.replace("_", " ").title(),
                    default_value=float_list,
                    size=2,
                    speed=0.1,
                    parent=parent,
                    min_value=FLOAT_MIN,
                    max_value=FLOAT_MAX,
                    callback=lambda s, v: setattr(node, attr, (v[0], v[1]))
                )
                return
            except (TypeError, ValueError):
                print("TypeError, ValueError, Type or Value not found.")

        try:
            val_as_float = float(value)
            pygui.add_drag_float(label = attr.replace("_", " ").title(),
                                 default_value=val_as_float, parent=parent,
                                 min_value=FLOAT_MIN,
                                 max_value=FLOAT_MAX,
                                 callback=lambda s, v: setattr(node, attr, v))
        
        except (TypeError, ValueError):
            print("TypeError, ValueError, Type or Value not found.")




    def _setup_dpg(self):
        pygui.create_viewport(title="KodEngine Editor", width=1400, height=900)
        pygui.setup_dearpygui()
        pygui.show_viewport()
        pygui.set_primary_window("Primary Window", True)

    def push_frame(self, frame):
        if pygui.does_item_exist("engine_texture"):
            try:
                pygui.set_value("engine_texture", frame.flatten())
            except Exception as e:
                pass

def main():
    editor = KodEditor()
    editor.run()

if __name__ == "__main__":
    main()
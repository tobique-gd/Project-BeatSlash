import dearpygui.dearpygui as pygui
import pygame
import numpy as np
from pathlib import Path

from KodEngine.engine import Kod, Nodes, Scenes, Scripts, NodeComponents
from BeatSlash.scripts.player import Player
from KodEngine.editor import ResourceManager

BASE_DIR = Path("BeatSlash")

class KodEditor:
    def __init__(self):
        self.settings = Kod.Settings()
        self.initial_res = (640, 360)
        self.settings.window_settings["internal_viewport_resolution"] = self.initial_res
        self.app = Kod.App(self.settings, editor_mode=True)
        
        self.root = Nodes.Node2D()
        self.root.name = "World"

        player_node = Nodes.CharacterBody2D()
        player_node.script = Player(player_node)
        player_node.name = "Player"

        idle_front_animation = NodeComponents.SpriteAnimation("Idle_Front", pygame.image.load(str(BASE_DIR / "assets/textures/spritesheets/player/idle_front.png")).convert_alpha(), (17, 27), 4, True, 4)
        idle_front_animation.spritesheet_path = str(BASE_DIR / "assets/textures/spritesheets/player/idle_front.png")
        idle_back_animation = NodeComponents.SpriteAnimation("Idle_Back", pygame.image.load(str(BASE_DIR / "assets/textures/spritesheets/player/idle_back.png")).convert_alpha(), (17, 27), 4, True, 4)
        idle_back_animation.spritesheet_path = str(BASE_DIR / "assets/textures/spritesheets/player/idle_back.png")
        idle_side_animation = NodeComponents.SpriteAnimation("Idle_Side", pygame.image.load(str(BASE_DIR / "assets/textures/spritesheets/player/idle_side.png")).convert_alpha(), (17, 27), 4, True, 4)
        idle_side_animation.spritesheet_path = str(BASE_DIR / "assets/textures/spritesheets/player/idle_side.png")
        run_front_animation = NodeComponents.SpriteAnimation("Run_Front", pygame.image.load(str(BASE_DIR / "assets/textures/spritesheets/player/run_front.png")).convert_alpha(), (17, 27), 8, True, 12)
        run_front_animation.spritesheet_path = str(BASE_DIR / "assets/textures/spritesheets/player/run_front.png")

        player_sprite = Nodes.AnimatedSprite2D()

        player_sprite.add_animation(idle_front_animation)
        player_sprite.add_animation(idle_back_animation)
        player_sprite.add_animation(idle_side_animation)
        player_sprite.add_animation(run_front_animation)
        player_sprite.play("Idle_Front")

        player_camera = Nodes.Camera2D()



        self.root.add_child(player_node)
        player_node.add_child(player_sprite)
        player_node.add_child(player_camera)

        sprite2 = Nodes.Sprite2D()
        sprite2.texture = pygame.image.load(BASE_DIR / "assets/textures/dmimage.png").convert_alpha()
        sprite2.texture_path = str(BASE_DIR / "assets/textures/dmimage.png")
        sprite2.global_position = (0,0)
        sprite2.z_index = -1

        music_player = Nodes.AudioPlayer()
        music_player.audio = str(BASE_DIR / "assets/audio/Aftermath.mp3")

        self.root.add_child(music_player)
        music_player.play()


        self.root.add_child(sprite2)

        sc_save = Scenes.Scene("world_scene", self.root)
        current_scene = ResourceManager.SceneLoader.load("sc.kscn")

        ResourceManager.SceneLoader.save("sc.kscn", sc_save)


        self.camera = Nodes.Camera2D()
        
        self.root = getattr(current_scene, "root", None)
        if self.root is None:
            self.root = Nodes.Node2D()
        
        self.app.set_camera(self.camera)
        self.app.set_scene(current_scene)

        self.width, self.height = self.initial_res
        self.ui = EditorUI(self)

        

 

    def render_frame(self):
        if not self.app.screen:
            print("Error, no screen supplied. Stopping rendering")
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
            self.ui.check_resize()
            
            self._update_node(self.root, delta)

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

    def _update_node(self, node, delta):
        node._update(delta)

        for child in getattr(node, "_children", []):
            self._update_node(child, delta)

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

                self._draw_property(node, attr, value)

    def _draw_property(self, node, attr, value):
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
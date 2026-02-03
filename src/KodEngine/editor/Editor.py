#GENERAL IMPORTY
import dearpygui.dearpygui as pygui
import numpy as np
import pygame
import os

#EDITOR IMPORTS
from . import ui_components as UIComp

#ENGINE IMPORTS
from KodEngine.engine import Kod, Nodes, Scenes, Scripts, NodeComponents, ResourceManager

#SCRIPTS TODO: musim predelat protoze to je uplne na picu
from BeatSlash.scripts.player import Player

BASE_DIR = os.path.abspath("BeatSlash")

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

        idle_front_animation = NodeComponents.SpriteAnimation("Idle_Front", pygame.image.load(str(BASE_DIR + "/assets/textures/spritesheets/player/idle_front.png")).convert_alpha(), (17, 27), 4, True, 4)
        idle_front_animation.spritesheet_path = str(BASE_DIR + "/assets/textures/spritesheets/player/idle_front.png")
        idle_back_animation = NodeComponents.SpriteAnimation("Idle_Back", pygame.image.load(str(BASE_DIR + "/assets/textures/spritesheets/player/idle_back.png")).convert_alpha(), (17, 27), 4, True, 4)
        idle_back_animation.spritesheet_path = str(BASE_DIR + "/assets/textures/spritesheets/player/idle_back.png")
        idle_side_animation = NodeComponents.SpriteAnimation("Idle_Side", pygame.image.load(str(BASE_DIR + "/assets/textures/spritesheets/player/idle_side.png")).convert_alpha(), (17, 27), 4, True, 4)
        idle_side_animation.spritesheet_path = str(BASE_DIR + "/assets/textures/spritesheets/player/idle_side.png")
        run_front_animation = NodeComponents.SpriteAnimation("Run_Front", pygame.image.load(str(BASE_DIR + "/assets/textures/spritesheets/player/run_front.png")).convert_alpha(), (17, 27), 8, True, 12)
        run_front_animation.spritesheet_path = str(BASE_DIR + "/assets/textures/spritesheets/player/run_front.png")

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
        sprite2.texture = pygame.image.load(BASE_DIR + "/assets/textures/dmimage.png").convert_alpha()
        sprite2.texture_path = str(BASE_DIR + "/assets/textures/dmimage.png")
        sprite2.global_position = (0,0)
        sprite2.z_index = -1

        music_player = Nodes.AudioPlayer()
        music_player.audio = str(BASE_DIR + "/assets/audio/Aftermath.mp3")

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
            
            if self.app.current_scene:
                nodes_were_deleted = self.app.current_scene._process_deletion_queue()
                if nodes_were_deleted and hasattr(self, 'ui'):
                    self.ui._update_hierarchy()

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
        node.editor_update(delta)
        
        if getattr(node, "_queued_for_deletion", False):
            if self.app.current_scene and node not in self.app.current_scene.deletion_queue:
                self.app.current_scene.deletion_queue.append(node)

        for child in getattr(node, "_children", []):
            self._update_node(child, delta)

class UIState:
    def __init__(self):
        self.selected_node = None
        self.selectables = {}

class EditorUI:
    def __init__(self, editor: KodEditor):
        self.editor = editor
        self.state = UIState()
        self.viewport = UIComp.ViewportPanel(self)
        self.hierarchy = UIComp.HierarchyPanel(self)
        self.inspector = UIComp.InspectorPanel(self)
        self.dialogs = UIComp.NodeDialogs(self)

        pygui.create_context()
        self.viewport.create_texture()
        self._create_layout()
        self._setup_dpg()

        if pygui.does_item_exist("add_node_btn"):
            pygui.configure_item("add_node_btn", enabled=False)

    def _create_layout(self):
        with pygui.window(tag="Primary Window"):
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
                            pygui.add_text("Console", color=(150, 150, 150))
                            pygui.add_separator()
                            pygui.add_text("[Log]: Manual Resize check active.", color=(0, 255, 0))

                    with pygui.child_window(border=True, tag="inspector_panel"):
                        self.inspector.build()

    def _setup_dpg(self):
        pygui.create_viewport(title="KodEngine Editor", width=1400, height=900)
        pygui.setup_dearpygui()
        pygui.show_viewport()
        pygui.set_primary_window("Primary Window", True)

    def check_resize(self):
        self.viewport.check_resize()

    def push_frame(self, frame):
        self.viewport.push_frame(frame)

    def _update_hierarchy(self):
        self.hierarchy.update_hierarchy()

    def _clear_inspector(self):
        self.inspector.clear()

def main():
    editor = KodEditor()
    editor.run()

if __name__ == "__main__":
    main()
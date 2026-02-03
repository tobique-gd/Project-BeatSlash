import pygame
from pathlib import Path

from ..KodEngine.engine import (Kod, Nodes, Scenes, NodeComponents)
from .scripts.player import Player

BASE_DIR = Path(__file__).parent

settings = Kod.Settings()
settings.window_settings["viewport_resolution"] = (1920, 1080)
settings.window_settings["internal_viewport_resolution"] = (640, 340)
settings.runtime_settings["FPS"] = 120

app = Kod.App(settings)

root = Nodes.Node2D()
root.name = "World"

player_node = Nodes.CharacterBody2D()
player_node.script = Player(player_node)
player_node.name = "Player"

idle_front_animation = NodeComponents.SpriteAnimation("Idle_Front", pygame.image.load(BASE_DIR / "assets/textures/spritesheets/player/idle_front.png").convert_alpha(), (17, 27), 4, True, 4)
idle_back_animation = NodeComponents.SpriteAnimation("Idle_Back", pygame.image.load(BASE_DIR / "assets/textures/spritesheets/player/idle_back.png").convert_alpha(), (17, 27), 4, True, 4)
idle_side_animation = NodeComponents.SpriteAnimation("Idle_Side", pygame.image.load(BASE_DIR / "assets/textures/spritesheets/player/idle_side.png").convert_alpha(), (17, 27), 4, True, 4)
run_front_animation = NodeComponents.SpriteAnimation("Run_Front", pygame.image.load(BASE_DIR / "assets/textures/spritesheets/player/run_front.png").convert_alpha(), (17, 27), 8, True, 12)

player_sprite = Nodes.AnimatedSprite2D()

player_sprite.add_animation(idle_front_animation)
player_sprite.add_animation(idle_back_animation)
player_sprite.add_animation(idle_side_animation)
player_sprite.add_animation(run_front_animation)
player_sprite.play("Idle_Front")

player_camera = Nodes.Camera2D()



root.add_child(player_node)
player_node.add_child(player_sprite)
player_node.add_child(player_camera)

sprite2 = Nodes.Sprite2D()
sprite2.texture = pygame.image.load(BASE_DIR / "assets/textures/dmimage.png").convert_alpha()
sprite2.global_position = (0,0)
sprite2.z_index = -1

music_player = Nodes.AudioPlayer()
music_player.audio = str(BASE_DIR / "assets/audio/Aftermath.mp3")

root.add_child(music_player)
music_player.play()


root.add_child(sprite2)


current_scene = Scenes.Scene("Main", root)
app.set_scene(current_scene)
app.set_camera(player_camera)

app.run()

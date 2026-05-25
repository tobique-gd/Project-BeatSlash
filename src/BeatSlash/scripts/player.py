from .common import mathlib
import pygame
import json
import os
from abc import ABC, abstractmethod
from typing import Optional

BASE_SPEED = 125
DASH_SPEED = 200
DASH_DURATION = 0.5
MAX_STAMINA = 100.0
STAMINA_UPGRADE_MULTIPLIER = 1.1
DASH_STAMINA_COST = 50.0
STAMINA_REGEN_PER_SECOND = 8.0

class PlayerState(ABC):
    def __init__(self, player):
        self.player = player

    @abstractmethod
    def on_enter(self): pass

    @abstractmethod
    def handle_input(self, event): return None

    @abstractmethod
    def update(self, delta, movement_input): return None

    @abstractmethod
    def on_exit(self): pass

    def play_animation(self, name):
        if name == self.player.current_animation_name:
            return
        self.player.animated_sprite.play(name)
        self.player.current_animation_name = name

    def get_anim(self, base):
        return f"a_{base}_{self.player.facing}"


class IdleState(PlayerState):
    def on_enter(self):
        pass

    def handle_input(self, event):
        return None

    def update(self, delta, movement_input):
        x, y = movement_input

        if x != 0 or y != 0:
            return RunState(self.player)

        self.player.node.velocity = (0, 0)

        self.play_animation(self.get_anim("idle"))
        return None

    def on_exit(self):
        pass


class RunState(PlayerState):
    def on_enter(self):
        pass

    def handle_input(self, event):
        return None

    def update(self, delta, movement_input):
        x, y = movement_input

        if x == 0 and y == 0:
            return IdleState(self.player)

        direction = mathlib.normalized((x, y))

        self.player.node.velocity = (
            direction[0] * BASE_SPEED * delta,
            direction[1] * BASE_SPEED * delta
        )

        self.player.last_direction = direction

        self.play_animation(self.get_anim("run"))
        return None

    def on_exit(self):
        pass


class DashState(PlayerState):
    def __init__(self, player):
        super().__init__(player)
        self.time_left = DASH_DURATION
        self.direction = player.last_direction

    def on_enter(self):
        self.time_left = DASH_DURATION

        self.player.stamina = max(0.0, self.player.stamina - DASH_STAMINA_COST)

        x, y = self.player.input_vector
        if x != 0 or y != 0:
            self.direction = mathlib.normalized((x, y))
        else:
            self.direction = self.player.last_direction

    def handle_input(self, event):
        return None

    def update(self, delta, movement_input):
        self.time_left -= delta

        self.player.node.velocity = (
            self.direction[0] * DASH_SPEED * delta,
            self.direction[1] * DASH_SPEED * delta
        )

        self.play_animation(self.get_anim("roll"))

        if self.time_left <= 0:
            x, y = movement_input
            if x != 0 or y != 0:
                return RunState(self.player)
            return IdleState(self.player)

        return None

    def on_exit(self):
        pass


class DeathState(PlayerState):
    def __init__(self, player):
        super().__init__(player)
        self.post_animation_time = 0.0
        self.animation_finished = False

    def on_enter(self):
        self.player.node.velocity = (0, 0)
        self.play_animation("a_death")

    def handle_input(self, event):
        return None

    def update(self, delta, movement_input):
        self.player.node.velocity = (0, 0)

        if not self.animation_finished:
            return None

        self.post_animation_time += delta

        if self.post_animation_time >= 1.0:
            self.player.node.change_scene_to("scenes/main_menu/start_screen.kscn")

        return None

    def on_exit(self):
        pass


def _load_player_progress():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    save_path = os.path.join(current_dir, "..", "data", "save.json")

    credits = 0
    stamina_level = 1

    try:
        if os.path.exists(save_path):
            with open(save_path, "r") as f:
                save = json.load(f)
            credits = int(save.get("player", {}).get("credits", 0))
            stamina_level = int(save.get("upgrades", {}).get("stamina", 1))
    except Exception:
        pass

    max_stamina = MAX_STAMINA * (STAMINA_UPGRADE_MULTIPLIER ** max(0, stamina_level - 1))
    return credits, max_stamina



def _ready(self):
    self.animated_sprite = self.node.get_node("AnimatedSprite2D")
    self.health_bar = self.node.get_node("UI/HealthBar")
    self.stamina_bar = self.node.get_node("UI/StaminaBar")
    self.current_animation_name = None

    _on_animation_finished._player = self
    if self.animated_sprite is not None:
        try:
            self.animated_sprite.connect("animation_finished", _on_animation_finished)
        except Exception:
            pass

    self.last_direction = (0, 1)
    self.input_vector = (0, 0)

    self.facing = "front"
    self.space_just_pressed = True

    self.health = 10
    self.health_bar.value = self.health
    self.credits, self.max_stamina = _load_player_progress()
    self.stamina = self.max_stamina
    if self.stamina_bar is not None:
        self.stamina_bar.max_value = self.max_stamina
        self.stamina_bar.value = self.stamina

    self.current_state = IdleState(self)
    self.current_state.on_enter()


def _input(self, event):
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_SPACE and self.space_just_pressed:
            if self.stamina >= DASH_STAMINA_COST:
                _switch_state(self, DashState(self))
            self.space_just_pressed = False

    if event.type == pygame.KEYUP:
        if event.key == pygame.K_SPACE:
            self.space_just_pressed = True


def _switch_state(self, new_state):
    if type(self.current_state) == type(new_state):
        return
    self.current_state.on_exit()
    self.current_state = new_state
    self.current_state.on_enter()


def _get_movement_input(self):
    x, y = 0, 0
    keys = pygame.key.get_pressed()

    if keys[pygame.K_w]:
        y -= 1
    if keys[pygame.K_s]:
        y += 1
    if keys[pygame.K_a]:
        x -= 1
    if keys[pygame.K_d]:
        x += 1

    return (x, y)


def _update_facing(self):
    dx, dy = self.last_direction

    if abs(dx) > 0:
        self.facing = "side"
    elif dy < 0:
        self.facing = "back"
    else:
        self.facing = "front"

    if dx < 0:
        self.animated_sprite.flip_h = True
    elif dx > 0:
        self.animated_sprite.flip_h = False


def _process(self, delta):
    self.health_bar.value = self.health
    if isinstance(self.current_state, DeathState):
        self.current_state.update(delta, (0, 0))
        self.node.move_and_slide()
        return

    stamina_regen = STAMINA_REGEN_PER_SECOND * (self.max_stamina / MAX_STAMINA)
    self.stamina = min(self.max_stamina, self.stamina + (stamina_regen * delta))
    if self.stamina_bar is not None:
        self.stamina_bar.max_value = self.max_stamina
        self.stamina_bar.value = self.stamina

    if not hasattr(self, "credits"):
        self.credits, self.max_stamina = _load_player_progress()
        self.stamina = self.max_stamina
    movement_input = _get_movement_input(self)
    self.input_vector = movement_input

    if movement_input != (0, 0):
        self.last_direction = mathlib.normalized(movement_input)

    _update_facing(self)

    if self.health <= 0:
        _switch_state(self, DeathState(self))
        return

    new_state = self.current_state.update(delta, movement_input)
    if new_state:
        _switch_state(self, new_state)

    
    self.node.move_and_slide()

    try:
        if hasattr(self, "credits"):
            if not hasattr(self, "_last_credits") or self._last_credits != self.credits:
                credits_label = self.node.get_node("UI/CreditsLabel")
                if credits_label is not None:
                    try:
                        credits_label.text = str(self.credits)
                    except Exception:
                        pass
                self._last_credits = self.credits
    except Exception:
        pass


def _on_animation_finished(animation_name=None):
    if animation_name != "a_death":
        return

    player = getattr(_on_animation_finished, "_player", None)
    if player is None:
        return

    if not isinstance(player.current_state, DeathState):
        return

    player.current_state.post_animation_time = 0.0
    player.current_state.animation_finished = True


_on_animation_finished._player = None

from .common import mathlib
import pygame
from abc import ABC, abstractmethod
from typing import Optional


# ======================
# CONSTANTS
# ======================
BASE_SPEED = 125
DASH_SPEED = 200
DASH_DURATION = 0.6


# ======================
# STATE BASE CLASS
# ======================
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


# ======================
# IDLE STATE
# ======================
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


# ======================
# RUN STATE
# ======================
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


# ======================
# DASH STATE
# ======================
class DashState(PlayerState):
    def __init__(self, player):
        super().__init__(player)
        self.time_left = DASH_DURATION
        self.direction = player.last_direction

    def on_enter(self):
        self.time_left = DASH_DURATION

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


# ======================
# PLAYER METHODS
# ======================
def _ready(self):
    self.animated_sprite = self.node.get_node("AnimatedSprite2D")
    self.current_animation_name = None

    self.last_direction = (0, 1)
    self.input_vector = (0, 0)

    self.facing = "front"
    self.space_just_pressed = True

    self.current_state = IdleState(self)
    self.current_state.on_enter()


def _input(self, event):
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_SPACE and self.space_just_pressed:
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
    movement_input = _get_movement_input(self)
    self.input_vector = movement_input

    if movement_input != (0, 0):
        self.last_direction = mathlib.normalized(movement_input)

    _update_facing(self)


    new_state = self.current_state.update(delta, movement_input)
    if new_state:
        _switch_state(self, new_state)

    # Move
    self.node.move_and_slide()

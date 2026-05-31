from .common import mathlib
import pygame
import json
import os
import math
from abc import ABC, abstractmethod
from typing import Optional

from KodEngine.engine import Globals

BASE_SPEED = 125
DASH_SPEED = 200
DASH_DURATION = 0.5
MAX_STAMINA = 100.0
DASH_STAMINA_COST = 50.0
STAMINA_REGEN_PER_SECOND = 8.0
ATTACK_DURATION = 0.1
BASE_ATTACK_DAMAGE = 1
BASE_MAX_HEALTH = 10
PLAYER_ATTACK_KNOCKBACK_DISTANCE = 1.8
ENEMY_KNOCKBACK_DISTANCE = 3.0
KNOCKBACK_DECAY_RATE = 18.0
ATTACK_HURTBOX_OFFSET = 30.0
ATTACK_HURTBOX_MAX_DISTANCE = ATTACK_HURTBOX_OFFSET * 2.0
ATTACK_HURTBOX_HORIZONTAL_SIZE = (44.0, 24.0)
ATTACK_HURTBOX_VERTICAL_SIZE = (24.0, 44.0)
BASE_ARMOR = 1.0

WEAPON_IDLE_TIMEOUT = 8.0
WEAPON_CONCEAL_DURATION = 0.35
WEAPON_PIVOT_REST_POSITION = (0.0, -12.0)


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
            direction[0] * self.player.move_speed * delta,
            direction[1] * self.player.move_speed * delta
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
    defs_path = os.path.join(current_dir, "..", "data", "upgrades.json")
    save_path = os.path.join(current_dir, "..", "data", "save.json")

    credits = 0
    stamina_level = 1
    speed_level = 1
    damage_level = 1
    health_level = 1
    armor_level = 1
    upgrade_defs = {}

    try:
        if os.path.exists(defs_path):
            with open(defs_path, "r") as f:
                defs_data = json.load(f)
            upgrade_defs = {
                upgrade.get("id"): upgrade
                for upgrade in defs_data.get("upgrades", [])
                if upgrade.get("id")
            }
    except Exception:
        pass

    try:
        if os.path.exists(save_path):
            with open(save_path, "r") as f:
                save = json.load(f)
            credits = int(save.get("player", {}).get("credits", 0))
            stamina_level = int(save.get("upgrades", {}).get("stamina", 1))
            speed_level = int(save.get("upgrades", {}).get("speed", 1))
            damage_level = int(save.get("upgrades", {}).get("damage", 1))
            health_level = int(save.get("upgrades", {}).get("health", 1))
            armor_level = int(save.get("upgrades", {}).get("armor", 1))
    except Exception:
        pass

    stamina_multiplier = float(upgrade_defs.get("stamina", {}).get("effect_multiplier", 1.0))
    speed_multiplier = float(upgrade_defs.get("speed", {}).get("effect_multiplier", 1.0))
    damage_multiplier = float(upgrade_defs.get("damage", {}).get("effect_multiplier", 1.0))
    health_multiplier = float(upgrade_defs.get("health", {}).get("effect_multiplier", 1.0))
    armor_multiplier = float(upgrade_defs.get("armor", {}).get("effect_multiplier", 1.0))

    max_stamina = MAX_STAMINA * (stamina_multiplier ** max(0, stamina_level - 1))
    move_speed = BASE_SPEED * (speed_multiplier ** max(0, speed_level - 1))
    attack_damage = max(BASE_ATTACK_DAMAGE, int(math.ceil(BASE_ATTACK_DAMAGE * (damage_multiplier ** max(0, damage_level - 1)))))
    max_health = max(BASE_MAX_HEALTH, int(math.ceil(BASE_MAX_HEALTH * (health_multiplier ** max(0, health_level - 1)))))
    max_armor = BASE_ARMOR * (armor_multiplier ** max(0, armor_level - 1))
    return credits, max_stamina, move_speed, attack_damage, max_health, max_armor


def _ease_out_cubic(t):
    return 1.0 - pow(1.0 - t, 2.0)


def _lerp_tuple(start, end, t):
    return (
        start[0] + ((end[0] - start[0]) * t),
        start[1] + ((end[1] - start[1]) * t),
    )


def _get_mouse_world_position(self):
    mouse_x, mouse_y = pygame.mouse.get_pos()

    app = getattr(Globals, "APP", None)
    if app is not None and hasattr(app, "_calculate_cover_transform"):
        output_w, output_h = app.screen.get_size() if getattr(app, "screen", None) is not None else app.resolution
        scale_x, scale_y, offset_x, offset_y, _, _ = app._calculate_cover_transform(output_w, output_h)
        if scale_x != 0 and scale_y != 0:
            mouse_x = (float(mouse_x) - float(offset_x)) / float(scale_x)
            mouse_y = (float(mouse_y) - float(offset_y)) / float(scale_y)

    return (float(mouse_x), float(mouse_y))


def _resolve_attack_target(body):
    if body is None:
        return None

    if hasattr(body, "health"):
        return body

    return getattr(body, "runtime_script", None)


def _update_attack_area(self, dx, dy):
    attack_area = getattr(self, "attack_area", None)
    if attack_area is None:
        return

    attack_shape = getattr(self, "attack_shape", None)

    player_x, player_y = self.node.global_position
    distance = math.hypot(dx, dy)

    if distance <= 0.0:
        direction = self.last_direction if self.last_direction != (0, 0) else (0.0, 1.0)
        distance = 0.0
    else:
        direction = (dx / distance, dy / distance)

    blend = abs(direction[1])

    attack_shape_size = (
        ATTACK_HURTBOX_HORIZONTAL_SIZE[0] + ((ATTACK_HURTBOX_VERTICAL_SIZE[0] - ATTACK_HURTBOX_HORIZONTAL_SIZE[0]) * blend),
        ATTACK_HURTBOX_HORIZONTAL_SIZE[1] + ((ATTACK_HURTBOX_VERTICAL_SIZE[1] - ATTACK_HURTBOX_HORIZONTAL_SIZE[1]) * blend),
    )

    attack_distance = ATTACK_HURTBOX_OFFSET
    target_position = (
        player_x + (direction[0] * attack_distance),
        player_y + (direction[1] * attack_distance),
    )

    attack_area.global_position = target_position

    if attack_shape is not None:
        attack_shape.size = attack_shape_size
        attack_shape.position = (
            -attack_shape_size[0] / 2.0,
            -attack_shape_size[1] / 2.0,
        )


def _damage_attack_area(self):
    attack_area = getattr(self, "attack_area", None)
    if attack_area is None:
        return

    attack_position = getattr(attack_area, "global_position", self.node.global_position)
    player_x, player_y = self.node.global_position
    attack_dx = attack_position[0] - player_x
    attack_dy = attack_position[1] - player_y
    attack_distance = math.hypot(attack_dx, attack_dy)
    if attack_distance <= 0.0:
        attack_direction = self.last_direction if self.last_direction != (0, 0) else (0.0, 1.0)
    else:
        attack_direction = (attack_dx / attack_distance, attack_dy / attack_distance)

    overlapping_nodes = []
    overlapping_bodies = getattr(attack_area, "get_overlapping_bodies", lambda: [])()
    overlapping_areas = getattr(attack_area, "get_overlapping_areas", lambda: [])()
    if overlapping_bodies:
        overlapping_nodes.extend(overlapping_bodies)
    if overlapping_areas:
        overlapping_nodes.extend(overlapping_areas)

    if not overlapping_nodes:
        return

    damaged_targets = set()
    hit_anything = False
    for body in overlapping_nodes:
        if body is None or body is self.node:
            continue

        target = _resolve_attack_target(body)
        target_id = id(target) if target is not None else None
        if target is None or not hasattr(target, "health") or target_id in damaged_targets:
            continue

        target_node = getattr(target, "node", body)
        target_position = getattr(target_node, "global_position", None)
        if target_position is not None:
            knockback_dx = float(target_position[0]) - float(player_x)
            knockback_dy = float(target_position[1]) - float(player_y)
            knockback_distance = math.hypot(knockback_dx, knockback_dy)
            if knockback_distance <= 0.0:
                knockback_direction = attack_direction
            else:
                knockback_direction = (knockback_dx / knockback_distance, knockback_dy / knockback_distance)
        else:
            knockback_direction = attack_direction

        if hasattr(target, "take_damage"):
            try:
                target.take_damage(
                    self.attack_damage,
                    knockback_direction=(knockback_direction[0], knockback_direction[1]),
                    knockback_amount=ENEMY_KNOCKBACK_DISTANCE,
                )
            except TypeError:
                target.take_damage(self.attack_damage)
        else:
            target.health -= self.attack_damage

        if hasattr(target, "add_knockback"):
            target.add_knockback(knockback_direction, ENEMY_KNOCKBACK_DISTANCE)
        elif hasattr(target_node, "velocity"):
            target_node.velocity = (
                float(getattr(target_node, "velocity", (0, 0))[0]) + (knockback_direction[0] * ENEMY_KNOCKBACK_DISTANCE),
                float(getattr(target_node, "velocity", (0, 0))[1]) + (knockback_direction[1] * ENEMY_KNOCKBACK_DISTANCE),
            )

        damaged_targets.add(target_id)
        hit_anything = True


def take_damage(self, amount):
    self.health = max(0, self.health - int(amount) * self.armor)
    if self.health_bar is not None:
        self.health_bar.value = self.health


def _update_weapon_concealment(self, delta):
    if self.weapon_pivot is None:
        return

    if self.weapon_concealed:
        if not self.weapon_concealing:
            return
        self.weapon_conceal_elapsed += delta
        t = min(1.0, self.weapon_conceal_elapsed / WEAPON_CONCEAL_DURATION)
        eased = _ease_out_cubic(t)
        self.weapon_pivot.scale = (1.0 - eased, 1.0 - eased)
        self.weapon_pivot.position = _lerp_tuple(
            self.weapon_conceal_start_pos,
            WEAPON_PIVOT_REST_POSITION,
            eased
        )
        if t >= 1.0:
            self.weapon_concealing = False
            if self.weapon_sprite is not None:
                self.weapon_sprite.visible = False
    else:
        self.weapon_pivot.scale = (1.0, 1.0)
        self.weapon_pivot.position = WEAPON_PIVOT_REST_POSITION
        if self.weapon_sprite is not None:
            self.weapon_sprite.visible = True


def _begin_weapon_conceal(self):
    if self.weapon_concealed or self.weapon_concealing:
        return
    self.weapon_concealed = True
    self.weapon_concealing = True
    self.weapon_conceal_elapsed = 0.0
    if self.weapon_pivot is not None:
        self.weapon_conceal_start_pos = tuple(getattr(self.weapon_pivot, "position", WEAPON_PIVOT_REST_POSITION))
    else:
        self.weapon_conceal_start_pos = WEAPON_PIVOT_REST_POSITION


def _reveal_weapon(self):
    self.weapon_concealed = False
    self.weapon_concealing = False
    self.weapon_conceal_elapsed = 0.0
    if self.weapon_pivot is not None:
        self.weapon_pivot.scale = (1.0, 1.0)
        self.weapon_pivot.position = WEAPON_PIVOT_REST_POSITION
    if self.weapon_sprite is not None:
        self.weapon_sprite.visible = True


def _ready(self):
    self.animated_sprite = self.node.get_node("AnimatedSprite2D")
    self.weapon_pivot = self.node.get_node("WeaponPivot")
    self.weapon_sprite = self.weapon_pivot.get_node("Sprite2D") if self.weapon_pivot is not None else None
    self.attack_area = self.node.get_node("Hurtbox")
    if self.attack_area is None:
        self.attack_area = self.node.get_node("Area2D")
    self.attack_shape = None
    if self.attack_area is not None:
        self.attack_shape = self.attack_area.get_node("RectangleCollisionShape2D")
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
    self.attack_just_pressed = True
    self.attack_active = False
    self.attack_elapsed = 0.0
    self.attack_start_rotation = 0.0
    self.attack_rotation_delta = 180.0
    self.attack_mid_flipped = False
    self.weapon_sprite_base_flip_v = False
    self.weapon_side_offset = 0.0
    self.knockback_velocity = (0.0, 0.0)

    self.time_since_last_attack = 0.0
    self.weapon_concealed = False
    self.weapon_concealing = False
    self.weapon_conceal_elapsed = 0.0
    self.weapon_conceal_start_pos = (0.0, 0.0)

    self.health = BASE_MAX_HEALTH
    self.health_bar.value = self.health
    self.credits, self.max_stamina, self.move_speed, self.attack_damage, self.max_health, self.armor = _load_player_progress()
    self.health = self.max_health
    if self.health_bar is not None:
        self.health_bar.max_value = self.max_health
        self.health_bar.value = self.health
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

    if event.type == pygame.MOUSEBUTTONDOWN:
        if event.button == 1 and self.attack_just_pressed and not self.attack_active:
            if self.weapon_concealed or self.weapon_concealing:
                _reveal_weapon(self)
                self.time_since_last_attack = 0.0
                self.attack_just_pressed = False
                return

            self.attack_active = True
            self.attack_elapsed = 0.0
            self.attack_start_rotation = getattr(self.weapon_pivot, "rotation", 0.0)
            self.attack_rotation_delta = -180.0 if self.weapon_side_offset == 0.0 else 180.0
            self.attack_mid_flipped = False
            if self.weapon_sprite is not None:
                self.weapon_sprite_base_flip_v = getattr(self.weapon_sprite, "flip_v", False)
            self.attack_just_pressed = False
            self.time_since_last_attack = 0.0
            mouse_x, mouse_y = _get_mouse_world_position(self)
            dx = mouse_x - self.node.global_position[0]
            dy = mouse_y - self.node.global_position[1]
            _update_attack_area(self, dx, dy)
            _damage_attack_area(self)

    if event.type == pygame.KEYUP:
        if event.key == pygame.K_SPACE:
            self.space_just_pressed = True

    if event.type == pygame.MOUSEBUTTONUP:
        if event.button == 1:
            self.attack_just_pressed = True


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
    if self.weapon_pivot is None:
        self.weapon_pivot = self.node.get_node("WeaponPivot")
    if self.weapon_sprite is None and self.weapon_pivot is not None:
        self.weapon_sprite = self.weapon_pivot.get_node("Sprite2D")

    mouse_x, mouse_y = _get_mouse_world_position(self)

    app = getattr(Globals, "APP", None)

    self.health_bar.value = self.health
    if isinstance(self.current_state, DeathState):
        self.current_state.update(delta, (0, 0))
        self.node.move_and_slide()
        return

    if app is not None and hasattr(app, "resolve_camera") and hasattr(app, "renderer"):
        camera = app.resolve_camera()
        zoom = getattr(camera, "zoom", 1.0)
        if isinstance(zoom, (list, tuple)):
            zoom = zoom[0] if len(zoom) > 0 else 1.0

        try:
            zoom = max(0.05, float(zoom))
        except Exception:
            zoom = 1.0

        viewport_size = getattr(app, "internal_resolution", app.configuration.project_settings["window"]["internal_viewport_resolution"])
        cam_x, cam_y = app.renderer._get_camera_world_position_for_viewport(camera, viewport_size, zoom)
        offset_x, offset_y = getattr(camera, "offset", (0, 0))
        node_x, node_y = self.node.global_position
        node_screen_x = (node_x - cam_x + offset_x) * zoom + (viewport_size[0] / 2.0)
        node_screen_y = (node_y - cam_y + offset_y) * zoom + (viewport_size[1] / 2.0)
        dx = float(mouse_x) - node_screen_x
        dy = float(mouse_y) - node_screen_y
    else:
        node_x, node_y = self.node.global_position
        dx = float(mouse_x) - float(node_x)
        dy = float(mouse_y) - float(node_y)

    self.weapon_angle = (math.degrees(math.atan2(dy, dx)) + 90.0) % 360.0

    if not self.weapon_concealed:
        self.time_since_last_attack += delta
        if self.time_since_last_attack >= WEAPON_IDLE_TIMEOUT:
            _begin_weapon_conceal(self)

    _update_weapon_concealment(self, delta)

    if self.attack_active:
        self.attack_elapsed += delta
        attack_progress = min(1.0, self.attack_elapsed / ATTACK_DURATION)
        eased_progress = _ease_out_cubic(attack_progress)
        self.weapon_pivot.rotation = self.attack_start_rotation + (self.attack_rotation_delta * eased_progress)

        if not self.attack_mid_flipped and attack_progress >= 0.5:
            self.attack_mid_flipped = True
            if self.weapon_sprite is not None:
                self.weapon_sprite.flip_v = not self.weapon_sprite_base_flip_v

        if attack_progress >= 1.0:
            self.attack_active = False
            self.weapon_side_offset = 180.0 if self.weapon_side_offset == 0.0 else 0.0
            self.weapon_pivot.rotation = self.weapon_angle + self.weapon_side_offset
            if self.weapon_sprite is not None:
                self.weapon_sprite.flip_v = not self.weapon_sprite_base_flip_v
    else:
        if not self.weapon_concealed:
            self.weapon_pivot.rotation = self.weapon_angle + self.weapon_side_offset

    if not self.attack_active:
        _update_attack_area(self, dx, dy)

    stamina_regen = STAMINA_REGEN_PER_SECOND * (self.max_stamina / MAX_STAMINA)
    self.stamina = min(self.max_stamina, self.stamina + (stamina_regen * delta))
    if self.stamina_bar is not None:
        self.stamina_bar.max_value = self.max_stamina
        self.stamina_bar.value = self.stamina

    if not hasattr(self, "credits"):
        self.credits, self.max_stamina, self.move_speed, self.attack_damage, self.max_health, self.armor = _load_player_progress()
        self.health = self.max_health
        if self.health_bar is not None:
            self.health_bar.max_value = self.max_health
            self.health_bar.value = self.health
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

    if hasattr(self, "knockback_velocity"):
        self.node.velocity = (
            float(self.node.velocity[0]) + float(self.knockback_velocity[0]),
            float(self.node.velocity[1]) + float(self.knockback_velocity[1]),
        )
        self.knockback_velocity = _lerp_tuple(self.knockback_velocity, (0.0, 0.0), min(1.0, delta * KNOCKBACK_DECAY_RATE))

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
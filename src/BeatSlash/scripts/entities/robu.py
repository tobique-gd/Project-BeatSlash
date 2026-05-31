import math
import random

from KodEngine.engine import Globals
from ..common import mathlib


def _lerp_rgb(start, end, t):
    return tuple(
        start[index] + (end[index] - start[index]) * t
        for index in range(3)
    )


class EnemyState:
    def __init__(self, controller):
        self.controller = controller

    def on_enter(self):
        pass

    def update(self, delta):
        return None

    def on_exit(self):
        pass


class SearchState(EnemyState):
    def __init__(self, controller):
        super().__init__(controller)
        self.change_timer = 0.0
        self.direction = (1.0, 0.0)

    def on_enter(self):
        self.change_timer = 0.0
        self.direction = self._pick_direction()
        self.controller.play_animation("a_idle")

    def _pick_direction(self):
        direction = (random.uniform(-1.0, 1.0), random.uniform(-0.5, 0.5))
        direction = mathlib.normalized(direction)
        if direction == (0, 0):
            direction = (1.0, 0.0)
        return direction

    def update(self, delta):
        if self.controller.player is not None:
            return ChaseState(self.controller)

        self.change_timer -= delta
        if self.change_timer <= 0.0:
            self.direction = self._pick_direction()
            self.change_timer = self.controller.search_direction_time

        self.controller.move(self.direction, self.controller.search_speed, delta)
        self.controller.play_animation("a_idle")
        return None


class ChaseState(EnemyState):
    def __init__(self, controller):
        super().__init__(controller)
        self.shoot_timer = 0.0
        self.close_timer = 0.0

    def on_enter(self):
        self.shoot_timer = 0.0
        self.close_timer = 0.0
        self.controller.play_animation("a_idle")

    def update(self, delta):
        player = self.controller.player
        if player is None:
            return SearchState(self.controller)

        dx = player.global_position[0] - self.controller.node.global_position[0]
        dy = player.global_position[1] - self.controller.node.global_position[1]
        distance = math.sqrt(dx * dx + dy * dy)
        if distance <= self.controller.charge_range:
            self.close_timer += delta
            self.controller.stop()
            if self.close_timer >= self.controller.charge_windup:
                return ChargeState(self.controller)
        else:
            self.close_timer = 0.0
            direction = mathlib.normalized(mathlib.direction_to(self.controller.node.global_position, player.global_position))
            self.controller.move(direction, self.controller.chase_speed, delta)
            self.controller.face_direction(direction)

        self.shoot_timer += delta
        if self.shoot_timer >= self.controller.chase_shot_interval:
            self.shoot_timer -= self.controller.chase_shot_interval
            self.controller.shoot_at_player(self.controller.chase_shot_count)

        self.controller.play_animation("a_idle")
        return None


class ChargeState(EnemyState):
    def __init__(self, controller):
        super().__init__(controller)
        self.timer = 0.0
        self.fired = False
        self.ground_pound_started = False

    def on_enter(self):
        self.timer = 0.0
        self.fired = False
        self.controller.stop()
        self.controller.play_animation("a_charge", loop=False)

    def update(self, delta):
        if self.ground_pound_started:
            self.timer += delta

            if not self.fired and self.timer >= 0.2:
                self.fired = True
                self.controller.burst_ring()

        self.controller.stop()
        return None


class RobuEnemyController:
    def __init__(self, node):
        self.node = node
        self.animated_sprite = None
        self.player_detect_area = None
        self.bullet_scene = self.node.preload("scenes/bullet.kscn")
        self.player = None
        self.health = 3
        self.dead = False
        self.hit_flash_time = 0.0
        self.hit_flash_duration = 0.16
        self.death_time = 0.0
        self.base_velocity = (0.0, 0.0)
        self.knockback_velocity = (0.0, 0.0)
        self.knockback_decay_rate = 18.0
        self.knockback_strength = 3.0

        self.search_speed = 25.0
        self.chase_speed = 50.0
        self.search_direction_time = 0.9
        self.chase_shot_interval = 0.7
        self.chase_shot_count = 1
        self.chase_bullet_spacing = 0.5
        self.chase_bullet_speed = 150.0
        self.charge_range = 72.0
        self.charge_windup = 0.5
        self.charge_ring_count = 14
        self.charge_ring_speed = 140.0
        self.charge_ring_spread = 0.0

        self.current_state = SearchState(self)

    def _ready(self):
        self.animated_sprite = self.node.get_node("AnimatedSprite2D")
        self.player_detect_area = self.node.get_node("PlayerDetectArea")

        if self.player_detect_area is not None:
            self.player_detect_area.connect("body_entered", self._on_player_detected)
            self.player_detect_area.connect("body_exited", self._on_player_lost)

        if self.animated_sprite is not None:
            self.animated_sprite.connect("animation_finished", self._on_animation_finished)

        self.current_state.on_enter()

    def _process(self, delta):
        self._frame_delta = delta
        if self.hit_flash_time > 0.0:
            self.hit_flash_time = max(0.0, self.hit_flash_time - delta)
            if self.animated_sprite is not None:
                flash_t = self.hit_flash_time / self.hit_flash_duration if self.hit_flash_duration > 0.0 else 0.0
                self.animated_sprite.tint = _lerp_rgb((1.0, 1.0, 1.0), (2.0, 2.0, 2.0), flash_t)
        elif self.animated_sprite is not None:
            self.animated_sprite.tint = (1.0, 1.0, 1.0)

        if self.dead:
            self.base_velocity = (0.0, 0.0)
            self._apply_motion(delta)

            self.death_time -= delta
            if self.death_time <= 0.0:
                self._die()
            return

        new_state = self.current_state.update(delta)
        if new_state is not None:
            self._switch_state(new_state)

    def _input(self, event):
        return None

    def _switch_state(self, new_state):
        if type(self.current_state) is type(new_state):
            return

        self.current_state.on_exit()
        self.current_state = new_state
        self.current_state.on_enter()

    def play_animation(self, name, loop=None):
        if self.animated_sprite is None:
            return

        anim = self._find_animation(name)
        if anim is not None and loop is not None:
            anim.loop = loop
        self.animated_sprite.play(name)

    def _find_animation(self, name):
        if self.animated_sprite is None:
            return None

        for animation in getattr(self.animated_sprite, "animations", []):
            if getattr(animation, "name", None) == name:
                return animation
        return None

    def move(self, direction, speed, delta):
        self.base_velocity = (direction[0] * speed * delta, direction[1] * speed * delta)
        self._apply_motion(delta)

    def stop(self):
        self.base_velocity = (0.0, 0.0)
        self._apply_motion(getattr(self, "_frame_delta", 0.0))

    def _apply_motion(self, delta):
        self.node.velocity = (
            self.base_velocity[0] + self.knockback_velocity[0],
            self.base_velocity[1] + self.knockback_velocity[1],
        )
        self.node.move_and_slide()

        decay_t = min(1.0, max(0.0, delta * self.knockback_decay_rate))
        self.knockback_velocity = (
            self.knockback_velocity[0] + ((0.0 - self.knockback_velocity[0]) * decay_t),
            self.knockback_velocity[1] + ((0.0 - self.knockback_velocity[1]) * decay_t),
        )

    def add_knockback(self, direction, amount=None):
        direction = mathlib.normalized(direction)
        if direction == (0, 0):
            direction = (1.0, 0.0)

        knockback_amount = self.knockback_strength if amount is None else float(amount)
        self.knockback_velocity = (
            self.knockback_velocity[0] + (direction[0] * knockback_amount),
            self.knockback_velocity[1] + (direction[1] * knockback_amount),
        )

    def face_direction(self, direction):
        if self.animated_sprite is None:
            return

        if direction[0] < 0:
            self.animated_sprite.flip_h = True
        elif direction[0] > 0:
            self.animated_sprite.flip_h = False

    def _spawn_bullet(self, direction, position=None, speed=None):
        if self.bullet_scene is None:
            return None

        bullet_node = self.bullet_scene.root.clone()
        if bullet_node is None:
            return None

        bullet_node.global_position = position if position is not None else self.node.global_position

        target_parent = self.node
        while getattr(target_parent, "_parent", None) is not None:
            target_parent = target_parent._parent
            if target_parent.__class__.__name__ == "YSort2D":
                break

        target_parent.add_child(bullet_node)

        bullet_script = getattr(bullet_node, "runtime_script", None)

        if bullet_script is not None and hasattr(bullet_script, "shoot"):
            if speed is not None and hasattr(bullet_script, "speed"):
                bullet_script.speed = speed
            bullet_script.shoot(direction)

        return bullet_node

    def shoot_at_player(self, count=1):
        if self.player is None:
            return

        direction = mathlib.normalized(mathlib.direction_to(self.node.global_position, self.player.global_position))
        if direction == (0, 0):
            direction = (1.0, 0.0)

        for index in range(max(1, int(count))):
            offset = (index - (count - 1) / 2.0) * self.chase_bullet_spacing
            shot_direction = mathlib.normalized((direction[0] + offset, direction[1]))
            if shot_direction == (0, 0):
                shot_direction = direction
            self._spawn_bullet(shot_direction, speed=self.chase_bullet_speed)

    def burst_ring(self):
        if self.player is not None:
            base_position = self.node.global_position
        else:
            base_position = self.node.global_position

        count = max(1, int(self.charge_ring_count))
        for index in range(count):
            angle = (math.tau * index) / count
            direction = (math.cos(angle), math.sin(angle))
            self._spawn_bullet(direction, position=base_position, speed=self.charge_ring_speed)

    def _on_animation_finished(self, animation_name=None):
        if not isinstance(self.current_state, ChargeState):
            return

        if animation_name == "a_charge":
            next_anim = self._find_animation("a_ground_pound")
            if next_anim is not None:
                next_anim.loop = False
            self.play_animation("a_ground_pound", loop=False)
            # signal the ChargeState that the ground pound animation has started
            if isinstance(self.current_state, ChargeState):
                self.current_state.ground_pound_started = True
                self.current_state.timer = 0.0
                self.current_state.fired = False
            return

        if animation_name != "a_ground_pound":
            return

        anim = self._find_animation(animation_name)
        if anim is not None:
            anim.loop = True

        if self.player is not None:
            self._switch_state(ChaseState(self))
        else:
            self._switch_state(SearchState(self))

    def _on_player_detected(self, body):
        if getattr(body, "name", None) == "Player":
            self.player = body
            if not isinstance(self.current_state, ChaseState) and not isinstance(self.current_state, ChargeState):
                self._switch_state(ChaseState(self))

    def _on_player_lost(self, body):
        if getattr(body, "name", None) == "Player":
            self.player = None
            self._switch_state(SearchState(self))

    def take_damage(self, amount, knockback_direction=None, knockback_amount=None):

        self.health -= int(amount)
        self.hit_flash_time = self.hit_flash_duration

        if knockback_direction is not None:
            self.add_knockback(knockback_direction, knockback_amount)

        if self.health <= 0:
            self.dead = True
            self.death_time = self.hit_flash_duration
            self.base_velocity = (0.0, 0.0)

    def _die(self):
        if self.dead:
            try:
                self.node.queue_free()
            except Exception:
                pass
            return

        try:
            self.node.queue_free()
        except Exception:
            pass


SCRIPT_CLASS = RobuEnemyController
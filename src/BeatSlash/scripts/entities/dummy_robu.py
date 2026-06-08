from ..common import mathlib


class DummyRobuEnemyController:
    def __init__(self, node):
        self.node = node
        self.animated_sprite = None
        self.health = 1
        self.dead = False
        self.hit_flash_time = 0.0
        self.hit_flash_duration = 0.16
        self.death_time = 0.0
        self.base_velocity = (0.0, 0.0)
        self.knockback_velocity = (0.0, 0.0)
        self.knockback_decay_rate = 18.0
        self.knockback_strength = 3.0

    def _ready(self):
        self.animated_sprite = self.node.get_node("AnimatedSprite2D")

        if self.animated_sprite is not None:
            self.play_animation("a_idle")

    def _process(self, delta):
        if self.hit_flash_time > 0.0:
            self.hit_flash_time = max(0.0, self.hit_flash_time - delta)
            if self.animated_sprite is not None:
                flash_t = self.hit_flash_time / self.hit_flash_duration if self.hit_flash_duration > 0.0 else 0.0
                self.animated_sprite.tint = (
                    1.0 + flash_t,
                    1.0 + flash_t,
                    1.0 + flash_t,
                )
        elif self.animated_sprite is not None:
            self.animated_sprite.tint = (1.0, 1.0, 1.0)

        if self.dead:
            self.base_velocity = (0.0, 0.0)
            self._apply_motion(delta)

            self.death_time -= delta
            if self.death_time <= 0.0:
                self._die()
            return

        self.base_velocity = (0.0, 0.0)
        self._apply_motion(delta)

    def _input(self, event):
        return None

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

    def take_damage(self, amount, knockback_direction=None, knockback_amount=None):
        if self.dead:
            return

        self.health -= int(amount)
        self.hit_flash_time = self.hit_flash_duration

        if knockback_direction is not None:
            self.add_knockback(knockback_direction, knockback_amount)

        if self.health <= 0:
            self.dead = True
            self.death_time = self.hit_flash_duration
            self.base_velocity = (0.0, 0.0)

    def _die(self):
        try:

            self.node.queue_free()
        except Exception:
            pass


SCRIPT_CLASS = DummyRobuEnemyController

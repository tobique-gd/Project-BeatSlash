from ..common import mathlib


class BulletController:
    def __init__(self, node):
        self.node = node
        self.speed = 260.0
        self.life_time = 3.0
        self.alive_time = 0.0
        self.direction = (0.0, 0.0)
        self.active = False
        self.damage = 1
        self.has_hit = False

    def _input(self, event):
        pass

    def shoot(self, direction):
        direction = mathlib.normalized(direction)
        if direction == (0, 0):
            direction = (1.0, 0.0)

        self.direction = direction
        self.active = True
        self.alive_time = 0.0
        self.has_hit = False

    def _ready(self):

        area = self.node.get_node("Area2D")
        if area is not None:
            try:
                area.connect("body_entered", self._on_body_entered)
            except Exception:
                pass

    def _on_body_entered(self, body):
        if body is None or self.has_hit:
            return

        target = body
        if not hasattr(target, "health"):
            target = getattr(body, "runtime_script", None)

        if target is not None and hasattr(target, "health"):
            if hasattr(target, "take_damage"):
                target.take_damage(self.damage)
            else:
                target.health -= self.damage
            self.has_hit = True
    

    def _process(self, delta):
        if not self.active:
            return

        self.alive_time += delta
        if self.alive_time >= self.life_time:
            self.node.queue_free()
            return

        self.node.velocity = (
            self.direction[0] * self.speed * delta,
            self.direction[1] * self.speed * delta,
        )
        self.node.move_and_slide()


SCRIPT_CLASS = BulletController
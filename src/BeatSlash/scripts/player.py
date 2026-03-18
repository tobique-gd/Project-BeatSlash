from .common import mathlib
import pygame

SPEED = 150


def _ready(self):
    self.animated_sprite = self.node.get_node("AnimatedSprite2D")
    self.last_direction = (0, 1)


def _process(self, delta):
    keys = pygame.key.get_pressed()
    x, y = 0, 0

    if keys[pygame.K_w]:
        y -= 1
    if keys[pygame.K_s]:
        y += 1
    if keys[pygame.K_a]:
        x -= 1
        self.animated_sprite.flip_h = True
    if keys[pygame.K_d]:
        x += 1
        self.animated_sprite.flip_h = False

    if x != 0 or y != 0:
        self.animated_sprite.play("Run_Front")
        direction = mathlib.normalized((x, y))
        self.node.velocity = (
            direction[0] * SPEED * delta,
            direction[1] * SPEED * delta
        )
        self.last_direction = direction
    else:
        self.node.velocity = (0, 0)
        dx, dy = self.last_direction

        if abs(dx) > 0:
            self.animated_sprite.play("Idle_Side")
        elif dy < 0:
            self.animated_sprite.play("Idle_Back")
        else:
            self.animated_sprite.play("Idle_Front")

    self.node.move_and_slide()


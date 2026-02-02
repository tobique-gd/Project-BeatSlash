from KodEngine.engine.Scripts import Script
from .common import mathlib
import pygame

class Player(Script):
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
            dir = mathlib.normalized((x, y))
            self.node.position = (
                self.node.position[0] + dir[0] * self.SPEED * delta,
                self.node.position[1] + dir[1] * self.SPEED * delta
            )
            self.last_direction = dir
        else:
            dx, dy = self.last_direction

            if abs(dx) > 0:
                self.animated_sprite.play("Idle_Side")
            elif dy < 0:
                self.animated_sprite.play("Idle_Back")
            else:
                self.animated_sprite.play("Idle_Front")


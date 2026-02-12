import pygame
from .Resources import CollisionRectangleShape
from . import Nodes

class PhysicsServer:
    def __init__(self, _configuration, _physics_objects) -> None:
        self.physics_bodies = _physics_objects
        self.substeps = _configuration.project_settings["physics"]["physics_substeps"]
        self.delta = 0
    
    def physics_process(self, delta):
        self.delta = delta / self.substeps
        
        for substep in range(self.substeps):
            for body in self.physics_bodies:
                self.resolve_physics_step_x(body)
            
            for body in self.physics_bodies:
                self.resolve_physics_step_y(body)            
            
    
    def resolve_physics_step_x(self, body):
        if body.collision_shape is None or not isinstance(body, (Nodes.DynamicBody2D, Nodes.KinematicBody2D)):
            return
        
       
        if isinstance(body, Nodes.DynamicBody2D):
            body.position = (body.position[0] + body.velocity[0] * self.delta, body.position[1])
        
        for other in self.physics_bodies:
            if other == body or other.collision_shape is None:
                continue
                
            if self.check_collision(body, other):
                self.resolve_collision_x(body, other)

    def resolve_physics_step_y(self, body):
        if body.collision_shape is None or not isinstance(body, (Nodes.DynamicBody2D, Nodes.KinematicBody2D)):
            return

        if isinstance(body, Nodes.DynamicBody2D):
            body.position = (body.position[0], body.position[1] + body.velocity[1] * self.delta)

        for other in self.physics_bodies:
            if other == body or other.collision_shape is None:
                continue
                
            if self.check_collision(body, other):
                self.resolve_collision_y(body, other)

    def check_collision(self, body1, body2):
        shape1 = body1.collision_shape.shape
        shape2 = body2.collision_shape.shape
        
        if isinstance(shape1, CollisionRectangleShape) and isinstance(shape2, CollisionRectangleShape):
            pos1 = (
                body1.global_position[0] + body1.collision_shape.position[0],
                body1.global_position[1] + body1.collision_shape.position[1]
            )
            pos2 = (
                body2.global_position[0] + body2.collision_shape.position[0],
                body2.global_position[1] + body2.collision_shape.position[1]
            )
            
            return (pos1[0] < pos2[0] + shape2.size[0] and
                    pos1[0] + shape1.size[0] > pos2[0] and
                    pos1[1] < pos2[1] + shape2.size[1] and
                    pos1[1] + shape1.size[1] > pos2[1])
        return False

    def resolve_collision_x(self, body, other):
        shape = body.collision_shape.shape
        other_shape = other.collision_shape.shape
        
        if isinstance(shape, CollisionRectangleShape) and isinstance(other_shape, CollisionRectangleShape):
            pos = body.global_position
            other_pos = other.global_position
            
            
            if body.velocity[0] > 0:
                body.position = (
                    other_pos[0] - shape.size[0] - body.collision_shape.position[0],
                    body.position[1]
                )
            else: 
                body.position = (
                    other_pos[0] + other_shape.size[0] - body.collision_shape.position[0],
                    body.position[1]
                )
            
            body.velocity = (0, body.velocity[1])

    def resolve_collision_y(self, body, other):
        shape = body.collision_shape.shape
        other_shape = other.collision_shape.shape
        
        if isinstance(shape, CollisionRectangleShape) and isinstance(other_shape, CollisionRectangleShape):
            pos = body.global_position
            other_pos = other.global_position
            
            
            if body.velocity[1] > 0:
                body.position = (
                    body.position[0],
                    other_pos[1] - shape.size[1] - body.collision_shape.position[1]
                )
            else:
                body.position = (
                    body.position[0],
                    other_pos[1] + other_shape.size[1] - body.collision_shape.position[1]
                )
            
            body.velocity = (body.velocity[0], 0)

    
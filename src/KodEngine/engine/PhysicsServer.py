from . import Nodes

# https://gamedev.stackexchange.com/questions/32545/what-is-the-mtv-minimum-translation-vector-in-sat-seperation-of-axis
# https://dyn4j.org/2010/01/sat/

class PhysicsSolver2D:
    def __init__(self, configuration) -> None:
        self.substeps = configuration.project_settings["physics"]["physics_substeps"]
        self.delta = 0.0
        self.physics_bodies = []

    def physics_process(self, physics_bodies, delta):
        self.physics_bodies = physics_bodies or []
        if self.substeps <= 0:
            self.substeps = 1

        self.delta = float(delta) / float(self.substeps)

        for substep_index in range(self.substeps):
            for body in self.physics_bodies:
                self.resolve_physics_step_x(body)

            for body in self.physics_bodies:
                self.resolve_physics_step_y(body)

    def _is_moving_body(self, body):
        return isinstance(body, (Nodes.DynamicBody2D, Nodes.KinematicBody2D))

    def _get_rect_shapes(self, body):
        if body is None:
            return []
        try:
            return body.get_nodes_by_type(Nodes.RectangleCollisionShape2D)
        except Exception:
            return []

    def _get_shape_world_position(self, body, shape):
        return (
            body.global_position[0] + shape.position[0],
            body.global_position[1] + shape.position[1],
        )

    def check_collision_pair(self, body1, shape1, body2, shape2):
        pos1 = self._get_shape_world_position(body1, shape1)
        pos2 = self._get_shape_world_position(body2, shape2)

        return (
            pos1[0] < pos2[0] + shape2.size[0]
            and pos1[0] + shape1.size[0] > pos2[0]
            and pos1[1] < pos2[1] + shape2.size[1]
            and pos1[1] + shape1.size[1] > pos2[1]
        )

    def _get_mtv(self, body, shape, other, other_shape):
        pos1 = self._get_shape_world_position(body, shape)
        pos2 = self._get_shape_world_position(other, other_shape)

        b1_left, b1_right = pos1[0], pos1[0] + shape.size[0]
        b1_top, b1_bottom = pos1[1], pos1[1] + shape.size[1]

        b2_left, b2_right = pos2[0], pos2[0] + other_shape.size[0]
        b2_top, b2_bottom = pos2[1], pos2[1] + other_shape.size[1]

        push_left = b2_left - b1_right
        push_right = b2_right - b1_left
        overlap_x = push_left if abs(push_left) < abs(push_right) else push_right

        push_up = b2_top - b1_bottom
        push_down = b2_bottom - b1_top
        overlap_y = push_up if abs(push_up) < abs(push_down) else push_down

        return overlap_x, overlap_y

    def resolve_physics_step_x(self, body):
        if body is None or not self._is_moving_body(body):
            return

        shapes = self._get_rect_shapes(body)
        if not shapes:
            return

        if isinstance(body, Nodes.DynamicBody2D):
            body.position = (body.position[0] + body.velocity[0] * self.delta, body.position[1])

        for other in self.physics_bodies:
            if other is body:
                continue

            other_shapes = self._get_rect_shapes(other)
            if not other_shapes:
                continue

            for shape in shapes:
                for other_shape in other_shapes:
                    if self.check_collision_pair(body, shape, other, other_shape):
                        overlap_x, overlap_y = self._get_mtv(body, shape, other, other_shape)
                        if abs(overlap_x) <= abs(overlap_y):
                            body.position = (body.position[0] + overlap_x, body.position[1])
                            if hasattr(body, 'velocity'):
                                body.velocity = (0, body.velocity[1])

    def resolve_physics_step_y(self, body):
        if body is None or not self._is_moving_body(body):
            return

        shapes = self._get_rect_shapes(body)
        if not shapes:
            return

        if isinstance(body, Nodes.DynamicBody2D):
            body.position = (body.position[0], body.position[1] + body.velocity[1] * self.delta)

        for other in self.physics_bodies:
            if other is body:
                continue

            other_shapes = self._get_rect_shapes(other)
            if not other_shapes:
                continue

            for shape in shapes:
                for other_shape in other_shapes:
                    if self.check_collision_pair(body, shape, other, other_shape):
                        overlap_x, overlap_y = self._get_mtv(body, shape, other, other_shape)
        
                        if abs(overlap_y) <= abs(overlap_x):
                            body.position = (body.position[0], body.position[1] + overlap_y)
                            if hasattr(body, 'velocity'):
                                body.velocity = (body.velocity[0], 0)
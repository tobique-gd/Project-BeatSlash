from . import Nodes
from collections import defaultdict
from . import ErrorHandler

class SpatialHashGrid:
    def __init__(self, cell_size=64):
        self.cell_size = cell_size
        self.cells = defaultdict(list)

    def clear(self):
        self.cells.clear()

    def _cell_coords(self, x, y):
        return (int(x) // self.cell_size, int(y) // self.cell_size)

    def insert_body(self, body, shapes):
        """Insert a body + its shapes into grid cells."""
        for shape in shapes:
            pos = (
                body.global_position[0] + shape.position[0],
                body.global_position[1] + shape.position[1],
            )

            x0, y0 = self._cell_coords(pos[0], pos[1])
            x1, y1 = self._cell_coords(
                pos[0] + shape.size[0],
                pos[1] + shape.size[1],
            )

            for gx in range(x0, x1 + 1):
                for gy in range(y0, y1 + 1):
                    self.cells[(gx, gy)].append((body, shape))

    def query(self, body, shape):
        """Return potential (body, shape) collision candidates."""
        pos = (
            body.global_position[0] + shape.position[0],
            body.global_position[1] + shape.position[1],
        )

        x0, y0 = self._cell_coords(pos[0], pos[1])
        x1, y1 = self._cell_coords(
            pos[0] + shape.size[0],
            pos[1] + shape.size[1],
        )

        results = set()

        for gx in range(x0, x1 + 1):
            for gy in range(y0, y1 + 1):
                for item in self.cells.get((gx, gy), []):
                    results.add(item)

        return results

class PhysicsSolver2D:
    def __init__(self, configuration) -> None:
        self.substeps = configuration.project_settings["physics"]["physics_substeps"]
        self.delta = 0.0
        self.physics_bodies = []

        self.grid = SpatialHashGrid(cell_size=64)

    def physics_process(self, physics_bodies, delta):
        self.physics_bodies = physics_bodies or []

        if self.substeps <= 0:
            self.substeps = 1

        self.delta = float(delta) / float(self.substeps)

        for _ in range(self.substeps):
            self.grid.clear()

            for body in self.physics_bodies:
                shapes = self._get_rect_shapes(body)
                if shapes:
                    self.grid.insert_body(body, shapes)

            for body in self.physics_bodies:
                self.resolve_physics_step_x(body)

            for body in self.physics_bodies:
                self.resolve_physics_step_y(body)

        self.resolve_area_overlaps()

    def _is_moving_body(self, body):
        return isinstance(body, (Nodes.DynamicBody2D, Nodes.KinematicBody2D))

    def _is_solid_body(self, body):
        return isinstance(body, (Nodes.StaticBody2D, Nodes.DynamicBody2D, Nodes.KinematicBody2D))

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

    def _layers_match(self, a, b):
        try:
            def to_masks(obj):
                layer_vals = getattr(obj, "collision_layers", None)
                mask_vals = getattr(obj, "collision_masks", None)

                def norm_values(val):
                    if val is None:
                        return []
                    if isinstance(val, (list, tuple)):
                        return list(val)[:10]
                    return [val]

                def interpret_index(x):
                    masks = set()
                    try:
                        xi = int(x)
                        if 1 <= xi <= 32:
                            masks.add(1 << (xi - 1))
                    except Exception:
                        pass
                    return masks

                layer_masks = set()
                for v in norm_values(layer_vals):
                    layer_masks.update(interpret_index(v))

                mask_masks = set()
                for v in norm_values(mask_vals):
                    mask_masks.update(interpret_index(v))

                return layer_masks, mask_masks

            a_layer_masks, a_mask_masks = to_masks(a)
            b_layer_masks, b_mask_masks = to_masks(b)

            a_in_b = any((al & bm) != 0 for al in a_layer_masks for bm in b_mask_masks)
            b_in_a = any((bl & am) != 0 for bl in b_layer_masks for am in a_mask_masks)

            return a_in_b and b_in_a

        except Exception:
            return False

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
            body.position = (
                body.position[0] + body.velocity[0] * self.delta,
                body.position[1],
            )

        for shape in shapes:
            candidates = self.grid.query(body, shape)

            for other, other_shape in candidates:
                if other is body:
                    continue
                if not self._is_solid_body(other):
                    continue
                if not self._layers_match(body, other):
                    continue
                if not self.check_collision_pair(body, shape, other, other_shape):
                    continue

                overlap_x, overlap_y = self._get_mtv(body, shape, other, other_shape)

                if abs(overlap_x) <= abs(overlap_y):
                    body.position = (body.position[0] + overlap_x, body.position[1])

                    if hasattr(body, "velocity"):
                        body.velocity = (0, body.velocity[1])

    def resolve_physics_step_y(self, body):
        if body is None or not self._is_moving_body(body):
            return

        shapes = self._get_rect_shapes(body)
        if not shapes:
            return

        if isinstance(body, Nodes.DynamicBody2D):
            body.position = (
                body.position[0],
                body.position[1] + body.velocity[1] * self.delta,
            )

        for shape in shapes:
            candidates = self.grid.query(body, shape)

            for other, other_shape in candidates:
                if other is body:
                    continue
                if not self._is_solid_body(other):
                    continue
                if not self._layers_match(body, other):
                    continue
                if not self.check_collision_pair(body, shape, other, other_shape):
                    continue

                overlap_x, overlap_y = self._get_mtv(body, shape, other, other_shape)

                if abs(overlap_y) <= abs(overlap_x):
                    body.position = (body.position[0], body.position[1] + overlap_y)

                    if hasattr(body, "velocity"):
                        body.velocity = (body.velocity[0], 0)

    def _has_any_shape_overlap(self, body, other):
        body_shapes = self._get_rect_shapes(body)
        other_shapes = self._get_rect_shapes(other)

        for a in body_shapes:
            for b in other_shapes:
                if self.check_collision_pair(body, a, other, b):
                    return True

        return False

    def resolve_area_overlaps(self):
        area_nodes = [
            node for node in self.physics_bodies
            if isinstance(node, Nodes.Area2D)
        ]

        previous_overlaps = {
            area: {
                "areas": list(getattr(area, "_overlapping_areas", [])),
                "bodies": list(getattr(area, "_overlapping_bodies", [])),
            }
            for area in area_nodes
        }

        for area in area_nodes:
            area._overlapping_areas = []
            area._overlapping_bodies = []

        for area in area_nodes:
            for other in self.physics_bodies:
                if other is area:
                    continue

                if isinstance(other, Nodes.Area2D):
                    if not area.collide_with_areas:
                        continue
                else:
                    if not area.collide_with_bodies:
                        continue

                if not self._layers_match(area, other):
                    continue

                if not self._has_any_shape_overlap(area, other):
                    continue

                if isinstance(other, Nodes.Area2D):
                    if other not in area._overlapping_areas:
                        area._overlapping_areas.append(other)
                else:
                    if other not in area._overlapping_bodies:
                        area._overlapping_bodies.append(other)

        for area in area_nodes:
            previous = previous_overlaps.get(area, {"areas": [], "bodies": []})

            self._emit_overlap_transition_signals(
                area,
                previous["bodies"],
                area._overlapping_bodies,
                "body_entered",
                "body_exited",
            )

            self._emit_overlap_transition_signals(
                area,
                previous["areas"],
                area._overlapping_areas,
                "area_entered",
                "area_exited",
            )

    def _emit_overlap_transition_signals(self, area, previous_nodes, current_nodes, entered_signal, exited_signal):
        previous_set = set(previous_nodes)
        current_set = set(current_nodes)

        for node in current_set - previous_set:
            area.emit_signal(entered_signal, node)

        for node in previous_set - current_set:
            area.emit_signal(exited_signal, node)
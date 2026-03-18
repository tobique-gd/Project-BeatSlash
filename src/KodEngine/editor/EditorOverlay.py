from ..engine import Nodes
import math


class EditorOverlayRenderer:
    def __init__(self, editor):
        self.editor = editor
        self._always_visible_gizmo_types = (Nodes.Camera2D,)

    @property
    def _editor_colors(self):
        return self.editor.editor_settings.editor_settings["debug"]

    def should_draw_without_selection(self, node):
        if not isinstance(node, Nodes.Node2D):
            return False

        explicit_setting = self._resolve_editor_gizmo_flag(node)
        if explicit_setting is not None:
            return explicit_setting

        return isinstance(node, self._always_visible_gizmo_types)

    def _resolve_editor_gizmo_flag(self, node):
       
        for attr_name in (
            "editor_draw_gizmo_when_unselected",
            "_editor_draw_gizmo_when_unselected",
            "editor_always_draw_gizmo",
            "_editor_always_draw_gizmo",
        ):
            if hasattr(node, attr_name):
                return bool(getattr(node, attr_name))
        return None

    def _active_scene_camera(self, gizmo_nodes):
        camera_nodes = [node for node in gizmo_nodes if isinstance(node, Nodes.Camera2D)]
        if not camera_nodes:
            return None

        for camera in camera_nodes:
            if bool(getattr(camera, "current", False)):
                return camera

        return camera_nodes[0]

    def _draw_node_shape_gizmo(self, debug, node, *, camera_is_active=False, selected=False):
        if isinstance(node, Nodes.Camera2D):
            viewport_w, viewport_h = self.editor.initial_res
            if selected:
                color = self._editor_colors["default_gizmo_color"]
                line_width = 2
                z_index = 25
            else:
                color = self._editor_colors.get("default_camera_gizmo_color", (181, 102, 237))
                line_width = 3 if camera_is_active else 1
                z_index = 20
            debug.draw_rect(
                (
                    node.global_position[0] - node.offset[0] - viewport_w / 2.0,
                    node.global_position[1] - node.offset[1] - viewport_h / 2.0,
                    viewport_w,
                    viewport_h,
                ),
                color=color,
                width=line_width,
                space="world",
                draw_pass="after_scene",
                z_index=z_index,
            )
            return

        if isinstance(node, Nodes.Sprite2D) and node.texture:
            debug.draw_rect(
                (
                    node.global_position[0] + node.offset[0],
                    node.global_position[1] + node.offset[1],
                    node.texture.get_width(),
                    node.texture.get_height(),
                ),
                color=self._editor_colors["default_gizmo_color"],
                space="world",
                draw_pass="after_scene",
                z_index=20,
            )
            return

        if isinstance(node, Nodes.AnimatedSprite2D) and node.current_animation:
            animation_texture = node.current_animation.get_current_frame_rect()
            debug.draw_rect(
                (
                    node.global_position[0] + node.offset[0],
                    node.global_position[1] + node.offset[1],
                    animation_texture.size[0],
                    animation_texture.size[1],
                ),
                color=self._editor_colors["default_gizmo_color"],
                space="world",
                draw_pass="after_scene",
                z_index=20,
            )
            return

        if isinstance(node, Nodes.RectangleCollisionShape2D) and node.size:
            debug.draw_rect(
                (
                    node.global_position[0],
                    node.global_position[1],
                    node.size[0],
                    node.size[1],
                ),
                color=self._editor_colors["default_collision_color"],
                space="world",
                draw_pass="after_scene",
                z_index=20,
            )

    def queue_debug_overlays(self, always_visible_nodes=None):
        if not hasattr(self.editor.app, "debug_renderer"):
            return

        debug = self.editor.app.debug_renderer
        if debug is None:
            return

        debug.clear_command_list()

        zoom = self.editor._get_camera_zoom()
        center_world_x = self.editor.camera.global_position[0] - self.editor.camera.offset[0]
        center_world_y = self.editor.camera.global_position[1] - self.editor.camera.offset[1]
        half_world_w = self.editor.width / (2.0 * zoom)
        half_world_h = self.editor.height / (2.0 * zoom)

        view_min_x = center_world_x - half_world_w
        view_max_x = center_world_x + half_world_w
        view_min_y = center_world_y - half_world_h
        view_max_y = center_world_y + half_world_h

        debug.draw_line(
            (view_min_x, 0.0),
            (view_max_x, 0.0),
            color=self._editor_colors["default_x_axis_color"],
            width=1,
            space="world",
            draw_pass="before_scene",
            z_index=-999,
        )
        debug.draw_line(
            (0.0, view_min_y),
            (0.0, view_max_y),
            color=self._editor_colors["default_y_axis_color"],
            width=1,
            space="world",
            draw_pass="before_scene",
            z_index=-999,
        )

        always_visible_nodes = always_visible_nodes or []
        selected_node = self.editor.ui.state.selected_node
        active_camera = self._active_scene_camera(always_visible_nodes)

        for node in always_visible_nodes:
            if node is selected_node and not isinstance(node, Nodes.Camera2D):
                continue
            self._draw_node_shape_gizmo(debug, node, camera_is_active=(node is active_camera))

        if selected_node and hasattr(selected_node, "global_position"):
            if isinstance(selected_node, Nodes.TileMap2D):
                self._draw_tilemap_grid(debug, selected_node, view_min_x, view_max_x, view_min_y, view_max_y)

            self._draw_node_shape_gizmo(
                debug,
                selected_node,
                camera_is_active=(selected_node is active_camera),
                selected=True,
            )
            debug.draw_gizmo(
                selected_node.global_position,
                highlight_axis=self.editor.gizmo.highlight_axis,
                spacing_scale=1.0,
                draw_pass="after_scene",
                z_index=30,
            )

    def _draw_tilemap_grid(self, debug, tilemap_node, view_min_x, view_max_x, view_min_y, view_max_y):
        tileset = getattr(tilemap_node, "tileset", None)
        tile_size = getattr(tileset, "tile_size", None)
        if not isinstance(tile_size, (list, tuple)) or len(tile_size) < 2:
            return

        try:
            cell_w = max(1, int(tile_size[0]))
            cell_h = max(1, int(tile_size[1]))
        except Exception:
            return

        origin_x = float(tilemap_node.global_position[0])
        origin_y = float(tilemap_node.global_position[1])

        min_col = int((view_min_x - origin_x) // cell_w) - 1
        max_col = int((view_max_x - origin_x) // cell_w) + 1
        min_row = int((view_min_y - origin_y) // cell_h) - 1
        max_row = int((view_max_y - origin_y) // cell_h) + 1

        # Keep grid density bounded when zoomed out to avoid per-frame spikes.
        zoom = max(0.001, float(self.editor._get_camera_zoom()))
        screen_cell_w = max(0.001, cell_w * zoom)
        screen_cell_h = max(0.001, cell_h * zoom)

        # Draw every Nth line when cells become tiny on screen.
        min_pixels_between_lines = 10.0
        col_step = max(1, int(math.ceil(min_pixels_between_lines / screen_cell_w)))
        row_step = max(1, int(math.ceil(min_pixels_between_lines / screen_cell_h)))

        visible_cols = max(1, max_col - min_col + 1)
        visible_rows = max(1, max_row - min_row + 1)
        max_lines_per_axis = 220
        if visible_cols // col_step > max_lines_per_axis:
            col_step = max(col_step, int(math.ceil(visible_cols / max_lines_per_axis)))
        if visible_rows // row_step > max_lines_per_axis:
            row_step = max(row_step, int(math.ceil(visible_rows / max_lines_per_axis)))

        grid_color = (95, 95, 95)

        start_col = min_col - (min_col % col_step)
        for col in range(start_col, max_col + 1, col_step):
            world_x = origin_x + col * cell_w
            debug.draw_line(
                (world_x, view_min_y),
                (world_x, view_max_y),
                color=grid_color,
                width=1,
                space="world",
                draw_pass="after_scene",
                z_index=15,
            )

        start_row = min_row - (min_row % row_step)
        for row in range(start_row, max_row + 1, row_step):
            world_y = origin_y + row * cell_h
            debug.draw_line(
                (view_min_x, world_y),
                (view_max_x, world_y),
                color=grid_color,
                width=1,
                space="world",
                draw_pass="after_scene",
                z_index=15,
            )

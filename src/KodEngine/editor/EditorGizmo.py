import dearpygui.dearpygui as pygui

from ..engine import Nodes


class EditorGizmoController:
    def __init__(self, editor):
        self.editor = editor
        self._drag_active = False
        self._drag_axis = None
        self._drag_start_mouse_screen = (0.0, 0.0)
        self._drag_start_node_world = (0.0, 0.0)
        self._left_mouse_was_down = False
        self._hover_axis = None

    @property
    def highlight_axis(self):
        if self._drag_active:
            return self._drag_axis
        return self._hover_axis

    def on_mouse_wheel(self, wheel_delta):
        if not self._is_mouse_over_viewport() or self._drag_active:
            return

        if isinstance(wheel_delta, (list, tuple)):
            if len(wheel_delta) == 0:
                return
            wheel_delta = wheel_delta[0]

        try:
            delta = float(wheel_delta)
        except Exception:
            return

        if abs(delta) < 0.0001:
            return

        before_mouse_world = self._viewport_mouse_world_position()
        if before_mouse_world is None:
            return

        current_zoom = self.editor._get_camera_zoom()
        new_zoom = current_zoom * (self.editor.zoom_step ** delta)
        self.editor._set_camera_zoom(new_zoom)

        after_mouse_world = self._viewport_mouse_world_position()
        if after_mouse_world is None:
            return

        cam_x, cam_y = self.editor.camera.global_position
        shift_x = before_mouse_world[0] - after_mouse_world[0]
        shift_y = before_mouse_world[1] - after_mouse_world[1]
        self.editor.camera.global_position = (cam_x + shift_x, cam_y + shift_y)

    

    def update_interaction(self):
        node = self.editor.ui.state.selected_node
        if not isinstance(node, Nodes.Node2D):
            self._drag_active = False
            self._left_mouse_was_down = pygui.is_mouse_button_down(pygui.mvMouseButton_Left)
            return

        mouse_screen = self._viewport_mouse_screen_position()
        mouse_down = pygui.is_mouse_button_down(pygui.mvMouseButton_Left)
        just_pressed = mouse_down and not self._left_mouse_was_down
        just_released = (not mouse_down) and self._left_mouse_was_down

        if just_pressed and mouse_screen is not None:
            axis = self._pick_gizmo_axis(node.global_position, mouse_screen)
            if axis is not None:
                self._drag_active = True
                self._drag_axis = axis
                self._drag_start_mouse_screen = mouse_screen
                self._drag_start_node_world = node.global_position

        if self._drag_active and mouse_screen is not None and mouse_down:
            start_mouse_x, start_mouse_y = self._drag_start_mouse_screen
            start_node_x, start_node_y = self._drag_start_node_world
            zoom = self.editor._get_camera_zoom()
            delta_x = (mouse_screen[0] - start_mouse_x) / zoom
            delta_y = (mouse_screen[1] - start_mouse_y) / zoom

            new_x, new_y = start_node_x, start_node_y
            if self._drag_axis in ("x", "xy"):
                new_x = start_node_x + delta_x
            if self._drag_axis in ("y", "xy"):
                new_y = start_node_y + delta_y

            node.global_position = (new_x, new_y)

        if self._drag_active and just_released:
            self._drag_active = False
            self._drag_axis = None
            self.editor.ui.inspector.update(node)

        self._left_mouse_was_down = mouse_down

    def _is_mouse_over_viewport(self):
        if not pygui.does_item_exist("viewport_image"):
            return False

        try:
            mouse_x, mouse_y = pygui.get_mouse_pos(local=False)
            rect_min_x, rect_min_y = pygui.get_item_rect_min("viewport_image")
            rect_w, rect_h = pygui.get_item_rect_size("viewport_image")
        except Exception:
            return False

        if rect_w <= 0 or rect_h <= 0:
            return False

        local_x = mouse_x - rect_min_x
        local_y = mouse_y - rect_min_y
        return 0 <= local_x <= rect_w and 0 <= local_y <= rect_h

    def _viewport_mouse_world_position(self):
        screen_pos = self._viewport_mouse_screen_position()
        if screen_pos is None:
            return None
        return self.editor._screen_to_world(screen_pos[0], screen_pos[1])

    def _viewport_mouse_screen_position(self):
        if not pygui.does_item_exist("viewport_image"):
            return None

        try:
            mouse_x, mouse_y = pygui.get_mouse_pos(local=False)
            rect_min_x, rect_min_y = pygui.get_item_rect_min("viewport_image")
            rect_w, rect_h = pygui.get_item_rect_size("viewport_image")
        except Exception:
            return None

        if rect_w <= 0 or rect_h <= 0:
            return None

        local_x = mouse_x - rect_min_x
        local_y = mouse_y - rect_min_y

        if not self._drag_active and (local_x < 0 or local_y < 0 or local_x > rect_w or local_y > rect_h):
            return None

        return (
            local_x * (self.editor.width / float(rect_w)),
            local_y * (self.editor.height / float(rect_h)),
        )

    def _pick_gizmo_axis(self, node_world_pos, mouse_screen_pos):
        nx, ny = node_world_pos
        mx, my = mouse_screen_pos
        sx, sy = self.editor._world_to_screen(nx, ny)
        spacing_scale = 1.0

        def in_rect(x, y, w, h, pad=0.0):
            return (x - pad) <= mx <= (x + w + pad) and (y - pad) <= my <= (y + h + pad)

        x_axis_center_x = sx + 60.0 * spacing_scale
        x_axis_center_y = sy
        y_axis_center_x = sx
        y_axis_center_y = sy + 60.0 * spacing_scale
        xy_axis_center_x = sx + 30.0 * spacing_scale
        xy_axis_center_y = sy + 30.0 * spacing_scale
        if in_rect(xy_axis_center_x - 16.0, xy_axis_center_y - 16.0, 32.0, 32.0, pad=4.0) or in_rect(
            sx - 15.5,
            sy - 15.5,
            31.0,
            31.0,
            pad=4.0,
        ):
            return "xy"

        if in_rect(x_axis_center_x - 32.0, x_axis_center_y - 16.0, 64.0, 32.0, pad=4.0):
            return "x"

        if in_rect(y_axis_center_x - 16.0, y_axis_center_y - 32.0, 32.0, 64.0, pad=4.0):
            return "y"

        return None

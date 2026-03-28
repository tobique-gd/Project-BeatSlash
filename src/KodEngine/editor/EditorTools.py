import dearpygui.dearpygui as pygui

from ..engine import Nodes


class TileMapPaintTool:
    def __init__(self, editor):
        self.editor = editor
        self._last_painted_key = None
        self._click_consumed = False
        self._right_mouse_was_down = False

    @property
    def click_consumed(self):
        return self._click_consumed

    def reset(self):
        self._last_painted_key = None
        self._click_consumed = False
        self._right_mouse_was_down = False

    def update(self):
        self._click_consumed = False
        node = self.editor.ui.state.selected_node
        right_mouse_down = pygui.is_mouse_button_down(pygui.mvMouseButton_Right)
        if not isinstance(node, Nodes.TileMap2D):
            self._last_painted_key = None
            self._right_mouse_was_down = right_mouse_down
            return

        mouse_screen = self.editor.gizmo._viewport_mouse_screen_position()
        left_mouse_down = pygui.is_mouse_button_down(pygui.mvMouseButton_Left)
        mouse_down = left_mouse_down or right_mouse_down
        just_pressed = (left_mouse_down and not self.editor.gizmo.left_mouse_was_down) or (
            right_mouse_down and not self._right_mouse_was_down
        )
        erase_mode = right_mouse_down

        if just_pressed and mouse_screen is not None:
            self._click_consumed = True

        if self.editor.gizmo.drag_active:
            self._right_mouse_was_down = right_mouse_down
            return

        self._try_paint(node, mouse_screen, mouse_down, just_pressed, erase_mode)
        self._right_mouse_was_down = right_mouse_down

    def _try_paint(self, node, mouse_screen, mouse_down, just_pressed, erase_mode):
        if mouse_screen is None or not mouse_down:
            return

        selected_layer = self.editor.get_selected_paint_tile_layer(node)
        if not isinstance(selected_layer, int):
            try:
                selected_layer = int(selected_layer)
            except Exception:
                selected_layer = 0

        if erase_mode:
            selected_tile_id = -1
        else:
            selected_tile_id = self.editor.get_selected_paint_tile_id(node)
            if not isinstance(selected_tile_id, int):
                return

            tileset = getattr(node, "tileset", None)
            if tileset is None:
                return

            if hasattr(tileset, "get_tile_by_id") and tileset.get_tile_by_id(selected_tile_id) is None:
                return

        world_pos = self.editor.gizmo._viewport_mouse_world_position()
        if world_pos is None:
            return

        node_world = getattr(node, "global_position", (0.0, 0.0))
        local_world = (world_pos[0] - node_world[0], world_pos[1] - node_world[1])
        tile_pos = node.world_to_tile(local_world)

        paint_key = (int(tile_pos[0]), int(tile_pos[1]), int(selected_layer), int(selected_tile_id))
        if paint_key == self._last_painted_key:
            if just_pressed:
                self._click_consumed = True
            return

        changed = node.set_tile_id(tile_pos, int(selected_tile_id), layer=int(selected_layer))
        if changed:
            self._last_painted_key = paint_key
            self._click_consumed = True


class EditorViewportToolController:
    def __init__(self, editor):
        self.editor = editor
        self.tilemap_paint = TileMapPaintTool(editor)

    @property
    def click_consumed(self):
        return self.tilemap_paint.click_consumed

    def reset(self):
        self.tilemap_paint.reset()

    def update(self):
        self.tilemap_paint.update()

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


class TileMapRectTool:
    def __init__(self, editor):
        self.editor = editor
        self._click_consumed = False
        self._left_mouse_was_down = False
        self._right_mouse_was_down = False
        self._dragging = False
        self._erase_drag = False
        self._rect_start: tuple | None = None
        self._rect_end: tuple | None = None

    @property
    def click_consumed(self) -> bool:
        return self._click_consumed

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    @property
    def rect_start(self) -> tuple | None:
        return self._rect_start

    @property
    def rect_end(self) -> tuple | None:
        return self._rect_end

    def reset(self):
        self._click_consumed = False
        self._left_mouse_was_down = False
        self._right_mouse_was_down = False
        self._dragging = False
        self._erase_drag = False
        self._rect_start = None
        self._rect_end = None

    def update(self):
        self._click_consumed = False

        node = self.editor.ui.state.selected_node
        if not isinstance(node, Nodes.TileMap2D):
            self._cancel_drag()
            self._left_mouse_was_down = pygui.is_mouse_button_down(pygui.mvMouseButton_Left)
            self._right_mouse_was_down = pygui.is_mouse_button_down(pygui.mvMouseButton_Right)
            return

        left_down = pygui.is_mouse_button_down(pygui.mvMouseButton_Left)
        right_down = pygui.is_mouse_button_down(pygui.mvMouseButton_Right)

        left_just_pressed  = left_down  and not self._left_mouse_was_down
        right_just_pressed = right_down and not self._right_mouse_was_down
        left_just_released  = not left_down  and self._left_mouse_was_down
        right_just_released = not right_down and self._right_mouse_was_down

        mouse_screen = self.editor.gizmo._viewport_mouse_screen_position()

        if (left_just_pressed or right_just_pressed) and mouse_screen is not None:
            if not self.editor.gizmo.drag_active:
                tile = self._screen_to_tile(node)
                if tile is not None:
                    self._dragging   = True
                    self._erase_drag = right_just_pressed
                    self._rect_start = tile
                    self._rect_end   = tile
                    self._click_consumed = True

        elif self._dragging and (left_down or right_down):
            tile = self._screen_to_tile(node)
            if tile is not None:
                self._rect_end = tile
            self._click_consumed = True

        elif self._dragging and (left_just_released or right_just_released):
            tile = self._screen_to_tile(node)
            if tile is not None:
                self._rect_end = tile
            self._commit(node)
            self._cancel_drag()
            self._click_consumed = True

        self._left_mouse_was_down  = left_down
        self._right_mouse_was_down = right_down

    def _screen_to_tile(self, node) -> tuple | None:
        world_pos = self.editor.gizmo._viewport_mouse_world_position()
        if world_pos is None:
            return None
        node_world = getattr(node, "global_position", (0.0, 0.0))
        local_world = (world_pos[0] - node_world[0], world_pos[1] - node_world[1])
        tp = node.world_to_tile(local_world)
        return (int(tp[0]), int(tp[1]))

    def _cancel_drag(self):
        self._dragging   = False
        self._erase_drag = False
        self._rect_start = None
        self._rect_end   = None

    def _commit(self, node):
        if self._rect_start is None or self._rect_end is None:
            return

        selected_layer = self.editor.get_selected_paint_tile_layer(node)
        if not isinstance(selected_layer, int):
            try:
                selected_layer = int(selected_layer)
            except Exception:
                selected_layer = 0

        if self._erase_drag:
            tile_id = -1
        else:
            tile_id = self.editor.get_selected_paint_tile_id(node)
            if not isinstance(tile_id, int):
                return
            tileset = getattr(node, "tileset", None)
            if tileset is None:
                return
            if hasattr(tileset, "get_tile_by_id") and tileset.get_tile_by_id(tile_id) is None:
                return

        x0 = min(self._rect_start[0], self._rect_end[0])
        x1 = max(self._rect_start[0], self._rect_end[0])
        y0 = min(self._rect_start[1], self._rect_end[1])
        y1 = max(self._rect_start[1], self._rect_end[1])

        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                node.set_tile_id((tx, ty), tile_id, layer=selected_layer)


class EditorViewportToolController:
    TOOL_PAINT = "paint"
    TOOL_RECT  = "rect"

    def __init__(self, editor):
        self.editor = editor
        self.tilemap_paint = TileMapPaintTool(editor)
        self.tilemap_rect  = TileMapRectTool(editor)
        self._active_tool  = self.TOOL_PAINT

    @property
    def active_tool(self) -> str:
        return self._active_tool

    def set_tool(self, tool_name: str):
        if tool_name not in (self.TOOL_PAINT, self.TOOL_RECT):
            raise ValueError(f"Unknown tool: {tool_name!r}")
        if tool_name != self._active_tool:
            self._get_tool(self._active_tool).reset()
        self._active_tool = tool_name

    def _get_tool(self, name):
        return self.tilemap_paint if name == self.TOOL_PAINT else self.tilemap_rect

    @property
    def click_consumed(self) -> bool:
        return self._get_tool(self._active_tool).click_consumed

    def reset(self):
        self.tilemap_paint.reset()
        self.tilemap_rect.reset()

    def update(self):
        self._get_tool(self._active_tool).update()
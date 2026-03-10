from ..engine import Nodes


class EditorOverlayRenderer:
    def __init__(self, editor):
        self.editor = editor

    def queue_debug_overlays(self):
        if not hasattr(self.editor.app, "debug_renderer"):
            return

        debug = self.editor.app.debug_renderer
        if debug is None:
            return
    
        debug.clear_command_list()

        if not self.editor.ui.state.selected_node:
            return

        node = self.editor.ui.state.selected_node
        if not hasattr(node, "global_position"):
            return

        if isinstance(node, Nodes.Camera2D):
            viewport_w, viewport_h = self.editor.initial_res
            debug.draw_rect(
                (
                    node.global_position[0] - node.offset[0] - viewport_w / 2.0,
                    node.global_position[1] - node.offset[1] - viewport_h / 2.0,
                    viewport_w,
                    viewport_h,
                ),
                color=self.editor.settings.editor_settings["default_gizmo_color"],
                space="world",
            )

        if isinstance(node, Nodes.Sprite2D) and node.texture:
            debug.draw_rect(
                (
                    node.global_position[0] + node.offset[0],
                    node.global_position[1] + node.offset[1],
                    node.texture.get_width(),
                    node.texture.get_height(),
                ),
                color=self.editor.settings.editor_settings["default_gizmo_color"],
                space="world",
            )

        if isinstance(node, Nodes.AnimatedSprite2D) and node.current_animation:
            animation_texture = node.current_animation.get_current_frame_rect()
            debug.draw_rect(
                (
                    node.global_position[0] + node.offset[0],
                    node.global_position[1] + node.offset[1],
                    animation_texture.size[0],
                    animation_texture.size[1],
                ),
                color=self.editor.settings.editor_settings["default_gizmo_color"],
                space="world",
            )

        if isinstance(node, Nodes.RectangleCollisionShape2D) and node.size:
            debug.draw_rect(
                (
                    node.global_position[0],
                    node.global_position[1],
                    node.size[0],
                    node.size[1],
                ),
                color=self.editor.settings.editor_settings["default_collision_color"],
                space="world",
            )

        debug.draw_gizmo(
            node.global_position,
            highlight_axis=self.editor.gizmo.highlight_axis,
            spacing_scale=1.0,
        )

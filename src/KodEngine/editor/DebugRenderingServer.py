from ..engine import ResourceServer
import os
import pygame

# Handles drawing primitives and textures for editor debug
class DebugRenderingServer:
    def __init__(self, configuration):
        self.configuration = configuration
        self._command_list = []
        self._command_sequence = 0

    def _queue_command(self, command_type, draw_pass="after_scene", z_index=0, **payload):
        self._command_list.append(
            {
                "type": command_type,
                "draw_pass": draw_pass,
                "z_index": int(z_index),
                "_seq": self._command_sequence,
                **payload,
            }
        )
        self._command_sequence += 1

    def _load_surface(self, relative_asset_path):
        base_dir = os.path.dirname(__file__)
        absolute_path = os.path.abspath(os.path.join(base_dir, relative_asset_path))
        resource = ResourceServer.ResourceLoader.load(absolute_path)

        if resource is None:
            return None

        if hasattr(resource, "get_texture"):
            return resource.get_texture()

        return None

    def clear_command_list(self):
        self._command_list.clear()
        self._command_sequence = 0

    def draw_rect(self, rect, color=(0, 255, 0), width=1, space="world", draw_pass="after_scene", z_index=0, alpha=255):
        self._queue_command(
            "rect",
            draw_pass=draw_pass,
            z_index=z_index,
            rect=rect,
            color=color,
            width=width,
            space=space,
            alpha=alpha,
        )

    def draw_line(self, from_pos, to_pos, color=(255, 255, 255), width=1, space="world", draw_pass="after_scene", z_index=0, alpha=255):
        self._queue_command(
            "line",
            draw_pass=draw_pass,
            z_index=z_index,
            from_pos=from_pos,
            to_pos=to_pos,
            color=color,
            width=width,
            space=space,
            alpha=alpha,
        )

    def draw_texture(self, texture, position, space="world", centered=False, no_zoom=False, screen_offset=(0.0, 0.0), draw_pass="after_scene", z_index=0):
        if texture is None:
            return

        self._queue_command(
            "texture",
            draw_pass=draw_pass,
            z_index=z_index,
            position=position,
            resource=texture,
            space=space,
            centered=centered,
            no_zoom=no_zoom,
            screen_offset=screen_offset,
        )

    def _lighten_surface(self, surface, amount=70):
        if surface is None:
            return None

        boosted = surface.copy().convert_alpha()
        boosted.fill((amount, amount, amount, 0), special_flags=pygame.BLEND_RGB_ADD)
        return boosted

    def draw_gizmo(self, position, space="world", highlight_axis=None, spacing_scale=1.0, draw_pass="after_scene", z_index=0):
        x_axis_texture = self._load_surface("assets/debug/gizmo/x_axis.png")
        y_axis_texture = self._load_surface("assets/debug/gizmo/y_axis.png")
        xy_axis_texture = self._load_surface("assets/debug/gizmo/xy_axis.png")
        origin_texture = self._load_surface("assets/debug/gizmo/origin.png")

        spacing_scale = float(spacing_scale)
        spacing_scale = max(0.001, spacing_scale)

        if highlight_axis == "x":
            x_axis_texture = self._lighten_surface(x_axis_texture)
        elif highlight_axis == "y":
            y_axis_texture = self._lighten_surface(y_axis_texture)
        elif highlight_axis == "xy":
            xy_axis_texture = self._lighten_surface(xy_axis_texture)

        self.draw_texture(
            origin_texture,
            (position[0], position[1]),
            space=space,
            centered=True,
            no_zoom=True,
            draw_pass=draw_pass,
            z_index=z_index,
        )
        self.draw_texture(
            x_axis_texture,
            (position[0], position[1]),
            space=space,
            centered=True,
            no_zoom=True,
            screen_offset=(60 * spacing_scale, 0.0),
            draw_pass=draw_pass,
            z_index=z_index + 1,
        )
        self.draw_texture(
            y_axis_texture,
            (position[0], position[1]),
            space=space,
            centered=True,
            no_zoom=True,
            screen_offset=(0.0, 60 * spacing_scale),
            draw_pass=draw_pass,
            z_index=z_index + 1,
        )
        self.draw_texture(
            xy_axis_texture,
            (position[0], position[1]),
            space=space,
            centered=True,
            no_zoom=True,
            screen_offset=(30 * spacing_scale, 30 * spacing_scale),
            draw_pass=draw_pass,
            z_index=z_index + 2,
        )

    def get_command_list(self):
        return list(self._command_list)

    def _world_to_screen(self, world_pos, camera):
        zoom = getattr(camera, "zoom", 1.0)
        if isinstance(zoom, (list, tuple)):
            zoom = zoom[0] if len(zoom) > 0 else 1.0
        try:
            zoom = float(zoom)
        except Exception:
            zoom = 1.0
        zoom = max(0.001, zoom)

        camera_offset_node_position = (
            (world_pos[0] - camera.global_position[0] + camera.offset[0]) * zoom,
            (world_pos[1] - camera.global_position[1] + camera.offset[1]) * zoom,
        )

        return (
            camera_offset_node_position[0]
            + self.configuration.project_settings["window"]["internal_viewport_resolution"][0] / 2.0,
            camera_offset_node_position[1]
            + self.configuration.project_settings["window"]["internal_viewport_resolution"][1] / 2.0,
        )

    def _extract_rgba(self, color, alpha):
        if not isinstance(color, (list, tuple)) or len(color) < 3:
            rgb = (255, 255, 255)
        else:
            rgb = (int(color[0]), int(color[1]), int(color[2]))

        if isinstance(color, (list, tuple)) and len(color) >= 4:
            final_alpha = int(color[3])
        else:
            final_alpha = int(alpha)

        final_alpha = max(0, min(255, final_alpha))
        return rgb, final_alpha

    def render(self, screen, pygame_module, camera, draw_pass="after_scene"):
        commands = [cmd for cmd in self._command_list if cmd.get("draw_pass", "after_scene") == draw_pass]
        commands.sort(key=lambda cmd: (int(cmd.get("z_index", 0)), int(cmd.get("_seq", 0))))

        for command in commands:
            match command.get("type"):
                case "rect":
                    x, y, w, h = command["rect"]
                    color = command.get("color", (0, 255, 0))
                    width = int(command.get("width", 1))
                    space = command.get("space", "world")
                    alpha = int(command.get("alpha", 255))
                    rgb, final_alpha = self._extract_rgba(color, alpha)

                    if space == "world":
                        zoom = getattr(camera, "zoom", 1.0)
                        if isinstance(zoom, (list, tuple)):
                            zoom = zoom[0] if len(zoom) > 0 else 1.0
                        try:
                            zoom = float(zoom)
                        except Exception:
                            zoom = 1.0
                        zoom = max(0.05, zoom)
                        sx, sy = self._world_to_screen((x, y), camera)
                        w = max(1, int(w * zoom))
                        h = max(1, int(h * zoom))
                    else:
                        sx, sy = x, y

                    rect = pygame_module.Rect(int(sx), int(sy), int(w), int(h))
                    if final_alpha >= 255:
                        pygame_module.draw.rect(screen, rgb, rect, width)
                    else:
                        overlay = pygame_module.Surface((max(1, rect.width), max(1, rect.height)), pygame_module.SRCALPHA)
                        pygame_module.draw.rect(
                            overlay,
                            (rgb[0], rgb[1], rgb[2], final_alpha),
                            pygame_module.Rect(0, 0, max(1, rect.width), max(1, rect.height)),
                            width,
                        )
                        screen.blit(overlay, rect.topleft)

                case "texture":
                    texture = command.get("resource")
                    if texture is None:
                        continue
                    pos = command.get("position", (0, 0))
                    space = command.get("space", "world")
                    centered = bool(command.get("centered", False))
                    no_zoom = bool(command.get("no_zoom", False))
                    screen_offset = command.get("screen_offset", (0.0, 0.0))
                    if space == "world":
                        zoom = getattr(camera, "zoom", 1.0)
                        if isinstance(zoom, (list, tuple)):
                            zoom = zoom[0] if len(zoom) > 0 else 1.0
                        try:
                            zoom = float(zoom)
                        except Exception:
                            zoom = 1.0
                        zoom = max(0.001, zoom)

                        pos = self._world_to_screen(pos, camera)

                        if (not no_zoom) and abs(zoom - 1.0) > 0.001:
                            target_w = max(1, int(texture.get_width() * zoom))
                            target_h = max(1, int(texture.get_height() * zoom))
                            texture = pygame_module.transform.scale(texture, (target_w, target_h))

                    pos = (pos[0] + float(screen_offset[0]), pos[1] + float(screen_offset[1]))

                    if centered:
                        pos = (pos[0] - texture.get_width() / 2.0, pos[1] - texture.get_height() / 2.0)

                    screen.blit(texture, pos)

                case "line":
                    from_pos = command.get("from_pos", (0, 0))
                    to_pos = command.get("to_pos", (0, 0))
                    color = command.get("color", (255, 255, 255))
                    width = int(command.get("width", 1))
                    space = command.get("space", "world")
                    alpha = int(command.get("alpha", 255))
                    rgb, final_alpha = self._extract_rgba(color, alpha)
                    if space == "world":
                        from_pos = self._world_to_screen(from_pos, camera)
                        to_pos = self._world_to_screen(to_pos, camera)

                    if final_alpha >= 255:
                        pygame.draw.line(screen, rgb, from_pos, to_pos, width)
                    else:
                        overlay = pygame_module.Surface(screen.get_size(), pygame_module.SRCALPHA)
                        pygame.draw.line(overlay, (rgb[0], rgb[1], rgb[2], final_alpha), from_pos, to_pos, width)
                        screen.blit(overlay, (0, 0))
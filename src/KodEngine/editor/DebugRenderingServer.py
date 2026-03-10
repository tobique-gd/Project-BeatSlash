from ..engine import ResourceServer
import os
import pygame


class DebugRenderingServer:
    def __init__(self, configuration):
        self.configuration = configuration
        self._command_list = []

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

    def draw_rect(self, rect, color=(0, 255, 0), width=1, space="world"):
        self._command_list.append(
            {
                "type": "rect",
                "rect": rect,
                "color": color,
                "width": width,
                "space": space,
            }
        )

    def draw_texture(self, texture, position, space="world", centered=False, no_zoom=False, screen_offset=(0.0, 0.0)):
        if texture is None:
            return

        self._command_list.append(
            {
                "type": "texture",
                "position": position,
                "resource": texture,
                "space": space,
                "centered": centered,
                "no_zoom": no_zoom,
                "screen_offset": screen_offset,
            }
        )

    def _lighten_surface(self, surface, amount=70):
        if surface is None:
            return None

        boosted = surface.copy().convert_alpha()
        boosted.fill((amount, amount, amount, 0), special_flags=pygame.BLEND_RGB_ADD)
        return boosted

    def draw_gizmo(self, position, space="world", highlight_axis=None, spacing_scale=1.0):
        x_axis_texture = self._load_surface("assets/debug/gizmo/x_axis.png")
        y_axis_texture = self._load_surface("assets/debug/gizmo/y_axis.png")
        xy_axis_texture = self._load_surface("assets/debug/gizmo/xy_axis.png")
        origin_texture = self._load_surface("assets/debug/gizmo/origin.png")

        try:
            spacing_scale = float(spacing_scale)
        except Exception:
            spacing_scale = 1.0
        spacing_scale = max(0.05, spacing_scale)

        if highlight_axis == "x":
            x_axis_texture = self._lighten_surface(x_axis_texture)
        elif highlight_axis == "y":
            y_axis_texture = self._lighten_surface(y_axis_texture)
        elif highlight_axis == "xy":
            xy_axis_texture = self._lighten_surface(xy_axis_texture)

        self.draw_texture(origin_texture, (position[0], position[1]), space=space, centered=True, no_zoom=True)
        self.draw_texture(x_axis_texture, (position[0], position[1]), space=space, centered=True, no_zoom=True, screen_offset=(60 * spacing_scale, 0.0))
        self.draw_texture(y_axis_texture, (position[0], position[1]), space=space, centered=True, no_zoom=True, screen_offset=(0.0, 60 * spacing_scale))
        self.draw_texture(xy_axis_texture, (position[0], position[1]), space=space, centered=True, no_zoom=True, screen_offset=(30 * spacing_scale, 30 * spacing_scale))

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
        zoom = max(0.05, zoom)

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

    def render(self, screen, pygame_module, camera):
        for command in self._command_list:
            match command.get("type"):
                case "rect":
                    x, y, w, h = command["rect"]
                    color = command.get("color", (0, 255, 0))
                    width = int(command.get("width", 1))
                    space = command.get("space", "world")

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

                    pygame_module.draw.rect(screen, color, pygame_module.Rect(int(sx), int(sy), int(w), int(h)), width)

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
                        zoom = max(0.05, zoom)

                        pos = self._world_to_screen(pos, camera)

                        if (not no_zoom) and abs(zoom - 1.0) > 0.001:
                            target_w = max(1, int(texture.get_width() * zoom))
                            target_h = max(1, int(texture.get_height() * zoom))
                            texture = pygame_module.transform.scale(texture, (target_w, target_h))

                    pos = (pos[0] + float(screen_offset[0]), pos[1] + float(screen_offset[1]))

                    if centered:
                        pos = (pos[0] - texture.get_width() / 2.0, pos[1] - texture.get_height() / 2.0)

                    screen.blit(texture, pos)

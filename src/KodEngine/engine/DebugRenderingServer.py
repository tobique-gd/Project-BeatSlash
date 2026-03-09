from . import ResourceServer
import os

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
        self._command_list.append({
            "type": "rect",
            "rect": rect,
            "color": color,
            "width": width,
            "space": space,
        })

    def draw_texture(self, texture, position, space="world", centered=False):
        if texture is None:
            return

        x, y = position
        if centered:
            x -= texture.get_width() / 2.0
            y -= texture.get_height() / 2.0

        self._command_list.append(
            {
                "type": "texture",
                "position": (x, y),
                "resource": texture,
                "space": space,
            }
        )

    def draw_gizmo(self, position, space="world"):
        x_axis_texture = self._load_surface("../editor/assets/debug/gizmo/x_axis.png")
        y_axis_texture = self._load_surface("../editor/assets/debug/gizmo/y_axis.png")
        xy_axis_texture = self._load_surface("../editor/assets/debug/gizmo/xy_axis.png")
        origin_texture = self._load_surface("../editor/assets/debug/gizmo/origin.png")

        self.draw_texture(origin_texture, (position[0], position[1]), space=space, centered=True)
        self.draw_texture(x_axis_texture, (position[0] + 60, position[1]), space=space, centered=True)
        self.draw_texture(y_axis_texture, (position[0], position[1] + 60), space=space, centered=True)
        self.draw_texture(xy_axis_texture, (position[0] + 30, position[1] + 30), space=space, centered=True)

    def get_command_list(self):
        return list(self._command_list)

    def _world_to_screen(self, world_pos, camera):
        camera_offset_node_position = (
            world_pos[0] - camera.global_position[0] + camera.offset[0],
            world_pos[1] - camera.global_position[1] + camera.offset[1],
        )

        return (
            camera_offset_node_position[0]
            + self.configuration.project_settings["window"]["internal_viewport_resolution"][0] / 2.0,
            camera_offset_node_position[1]
            + self.configuration.project_settings["window"]["internal_viewport_resolution"][1] / 2.0,
        )

    def render(self, screen, pygame, camera):
        for command in self._command_list:
            match command.get("type"):
                case "rect":
                    x, y, w, h = command["rect"]
                    color = command.get("color", (0, 255, 0))
                    width = int(command.get("width", 1))
                    space = command.get("space", "world")

                    if space == "world":
                        sx, sy = self._world_to_screen((x, y), camera)
                    else:
                        sx, sy = x, y

                    pygame.draw.rect(screen, color, pygame.Rect(int(sx), int(sy), int(w), int(h)), width)
                
                case "texture":
                    texture = command.get("resource")
                    if texture is None:
                        continue
                    pos = command.get("position", (0, 0))
                    space = command.get("space", "world")
                    if space == "world":
                        pos = self._world_to_screen(pos, camera)
                    screen.blit(texture, pos)

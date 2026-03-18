from . import Nodes
from . import Resources

#rendering works by sorting nodes by z-index and rendering them 
class Renderer2D:
    def __init__(self, _configuration, _pygame, _screen, _debug_renderer=None) -> None:
        self.configuration = _configuration
        self.pygame = _pygame
        self.screen = _screen
        self.debug_renderer = _debug_renderer
    
    def is_inside_viewport(self, object, camera, project_settings):
        texture = object.image
        if texture is None:
            return False

        zoom = self._get_camera_zoom()

        camera_center_x = camera.global_position[0] - camera.offset[0]
        camera_center_y = camera.global_position[1] - camera.offset[1]

        half_viewport_world_w = project_settings[0] / (2.0 * zoom)
        half_viewport_world_h = project_settings[1] / (2.0 * zoom)

        frustum_left = camera_center_x - half_viewport_world_w
        frustum_right = camera_center_x + half_viewport_world_w
        frustum_top = camera_center_y - half_viewport_world_h
        frustum_bottom = camera_center_y + half_viewport_world_h

        object_left = object.global_position[0] + object.offset[0]
        object_top = object.global_position[1] + object.offset[1]
        object_right = object_left + texture.get_width()
        object_bottom = object_top + texture.get_height()

        return not (
            object_right < frustum_left or
            object_left > frustum_right or
            object_bottom < frustum_top or
            object_top > frustum_bottom
        )
    
    def is_tile_inside_viewport(self, tile_world_x, tile_world_y, tile_width, tile_height, camera, project_settings):
        zoom = self._get_camera_zoom()
        camera_center_x = camera.global_position[0] - camera.offset[0]
        camera_center_y = camera.global_position[1] - camera.offset[1]

        half_viewport_world_w = project_settings[0] / (2.0 * zoom)
        half_viewport_world_h = project_settings[1] / (2.0 * zoom)

        frustum_left = camera_center_x - half_viewport_world_w
        frustum_right = camera_center_x + half_viewport_world_w
        frustum_top = camera_center_y - half_viewport_world_h
        frustum_bottom = camera_center_y + half_viewport_world_h

        tile_left = tile_world_x
        tile_top = tile_world_y
        tile_right = tile_left + tile_width
        tile_bottom = tile_top + tile_height

        return not (
            tile_right < frustum_left or
            tile_left > frustum_right or
            tile_bottom < frustum_top or
            tile_top > frustum_bottom
        )

    
        
    def render_frame(self, scene, _camera, renderable_nodes):
        self.camera = _camera
        self.screen.fill(self.configuration.editor_settings["debug"]["default_background_color"])

        if self.debug_renderer is not None:
            self.debug_renderer.render(self.screen, self.pygame, self.camera, draw_pass="before_scene")
        
        if scene != None:
            nodes = renderable_nodes
            nodes.sort(key=lambda node: (node.z_index))
            
            for renderable_object in nodes:
                self.render_node(renderable_object)

        if self.debug_renderer is not None:
            self.debug_renderer.render(self.screen, self.pygame, self.camera, draw_pass="after_scene")
        
        self.pygame.display.flip()

    #rendering accounts for camera transformation and offset
    def _get_camera_zoom(self):
        zoom = getattr(self.camera, "zoom", 1.0)

        if isinstance(zoom, (list, tuple)):
            zoom = zoom[0] if len(zoom) > 0 else 1.0

        try:
            zoom = float(zoom)
        except Exception:
            zoom = 1.0

        return max(0.05, zoom)

    def _collect_ysort_renderables(self, node, out):
        for child in getattr(node, "_children", []):
            if isinstance(child, (Nodes.Sprite2D, Nodes.TileMap2D)):
                out.append(child)

            self._collect_ysort_renderables(child, out)

    def render_node(self, node):
        if isinstance(node, Nodes.TileMap2D):
            self.render_tilemap(node)
            return
        
        if isinstance(node, Nodes.YSort2D):
            renderables = []
            self._collect_ysort_renderables(node, renderables)
            sorted_children = sorted(renderables, key=lambda child: child.global_position[1])
            for child in sorted_children:
                self.render_node(child)
            return

        #only render nodes that have an image
        if isinstance(node, Nodes.Sprite2D):
            tex = node.image
            if tex is None:
                return

            # this performs frustum culling to improve performace but im not sure if its actually faster
            if not self.is_inside_viewport(node, self.camera, self.configuration.project_settings["window"]["internal_viewport_resolution"]):
                return
            
        
            zoom = self._get_camera_zoom()

            camera_offset_node_position = (
                (node.global_position[0] - self.camera.global_position[0] + self.camera.offset[0]) * zoom,
                (node.global_position[1] - self.camera.global_position[1] + self.camera.offset[1]) * zoom,
            )

       
            camera_offset_centered = (
                camera_offset_node_position[0] + self.configuration.project_settings["window"]["internal_viewport_resolution"][0] / 2.0,
                camera_offset_node_position[1] + self.configuration.project_settings["window"]["internal_viewport_resolution"][1] / 2.0
            )

            camera_space_translation = (
                camera_offset_centered[0] + node.offset[0] * zoom,
                camera_offset_centered[1] + node.offset[1] * zoom,
            )

            if abs(zoom - 1.0) > 0.001:
                target_w = max(1, int(tex.get_width() * zoom))
                target_h = max(1, int(tex.get_height() * zoom))
                tex = self.pygame.transform.scale(tex, (target_w, target_h))

            self.screen.blit(tex, camera_space_translation)

    def render_tilemap(self, node):
        tileset = getattr(node, "tileset", None)
        tile_data = getattr(node, "tile_data", getattr(node, "_tile_data", None))
        bounds = getattr(node, "bounds", getattr(node, "_bounds", ((0, 0), (-1, -1))))

        if tileset is None or not isinstance(tile_data, list):
            return

        zoom = self._get_camera_zoom()
        (min_x, min_y), _ = bounds

        for row_index, row in enumerate(tile_data):
            if not isinstance(row, (list, tuple)):
                continue

            for column_index, tile_id in enumerate(row):
                try:
                    tile_id = int(tile_id)
                except Exception:
                    continue

                if tile_id < 0:
                    continue

                texture = tileset.get_tile_surface(tile_id)
                if texture is None:
                    continue

                tile_x = min_x + column_index
                tile_y = min_y + row_index
                world_x, world_y = node.tile_to_world((tile_x, tile_y))

                tile_world_x = node.global_position[0] + world_x
                tile_world_y = node.global_position[1] + world_y

                # tile doesnt have image so my normal frustum culling wont work so i have to do it manually here
                if not self.is_tile_inside_viewport(
                    tile_world_x,
                    tile_world_y,
                    texture.get_width(),
                    texture.get_height(),
                    self.camera,
                    self.configuration.project_settings["window"]["internal_viewport_resolution"],
                ):
                    continue

                camera_offset_node_position = (
                    (tile_world_x - self.camera.global_position[0] + self.camera.offset[0]) * zoom,
                    (tile_world_y - self.camera.global_position[1] + self.camera.offset[1]) * zoom,
                )

                camera_offset_centered = (
                    camera_offset_node_position[0] + self.configuration.project_settings["window"]["internal_viewport_resolution"][0] / 2.0,
                    camera_offset_node_position[1] + self.configuration.project_settings["window"]["internal_viewport_resolution"][1] / 2.0,
                )

                

                if abs(zoom - 1.0) > 0.001:
                    target_w = max(1, int(texture.get_width() * zoom))
                    target_h = max(1, int(texture.get_height() * zoom))
                    texture = self.pygame.transform.scale(texture, (target_w, target_h))

                self.screen.blit(texture, camera_offset_centered)


    def create_node_structure(self, node, nodes_array=None):
        if nodes_array is None:
            nodes_array = []

        if isinstance(node, (Nodes.Sprite2D, Nodes.TileMap2D)):
            nodes_array.append(node)

        for child in getattr(node, '_children', []):
            self.create_node_structure(child, nodes_array)

        return nodes_array
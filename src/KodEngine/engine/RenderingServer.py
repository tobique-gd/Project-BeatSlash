from . import Nodes
from . import Resources
from .ErrorHandler import ErrorHandler

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

    def _viewport_size(self):
        try:
            size = self.screen.get_size()
            if isinstance(size, (list, tuple)) and len(size) >= 2:
                return (int(size[0]), int(size[1]))
        except Exception:
            pass

        fallback = self.configuration.project_settings["window"].get("internal_viewport_resolution", (640, 360))
        return (int(fallback[0]), int(fallback[1]))

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

            viewport_size = self._viewport_size()

            # this performs frustum culling to improve performance but im not sure if its actually faster since i dont exactly know how sdl works and if the frustum check is more expensive than just rendering the texture
            if not self.is_inside_viewport(node, self.camera, viewport_size):
                return
            
        
            zoom = self._get_camera_zoom()

            camera_offset_node_position = (
                (node.global_position[0] - self.camera.global_position[0] + self.camera.offset[0]) * zoom,
                (node.global_position[1] - self.camera.global_position[1] + self.camera.offset[1]) * zoom,
            )

       
            camera_offset_centered = (
                camera_offset_node_position[0] + viewport_size[0] / 2.0,
                camera_offset_node_position[1] + viewport_size[1] / 2.0
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
        tile_layers = getattr(node, "tile_layers", getattr(node, "_tile_layers", None))
        bounds = getattr(node, "bounds", getattr(node, "_bounds", ((0, 0), (-1, -1))))

        if tileset is None:
            return

        if isinstance(tile_layers, dict):
            sorted_layers = []
            for layer_key, layer_data in tile_layers.items():
                if not isinstance(layer_data, list):
                    continue
                try:
                    layer_index = int(layer_key)
                except Exception:
                    continue
                sorted_layers.append((layer_index, layer_data))
            sorted_layers.sort(key=lambda item: item[0])
            layers_to_render = sorted_layers
        elif isinstance(tile_data, list):
            layers_to_render = [(0, tile_data)]
        else:
            return

        zoom = self._get_camera_zoom()
        viewport_size = self._viewport_size()
        (min_x, min_y), _ = bounds
        active_layer = getattr(node, "_editor_active_paint_layer", None)
        active_layer_index = int(active_layer) if isinstance(active_layer, int) else None
        selection_settings = self.configuration.editor_settings.get("selection", {})
        selected_node_id = selection_settings.get("selected_node_id") if isinstance(selection_settings, dict) else None
        is_selected_tilemap = isinstance(selected_node_id, int) and int(selected_node_id) == id(node)
        dim_non_active_layers = ErrorHandler.is_editor_mode() and is_selected_tilemap and active_layer_index is not None
        dim_factor = 0.45

        scaled_texture_cache = {}
        dimmed_texture_cache = {}

        for layer_index, layer_data in layers_to_render:
            is_dim_layer = bool(dim_non_active_layers and int(layer_index) != active_layer_index)
            for row_index, row in enumerate(layer_data):
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
                        viewport_size,
                    ):
                        continue

                    camera_offset_node_position = (
                        (tile_world_x - self.camera.global_position[0] + self.camera.offset[0]) * zoom,
                        (tile_world_y - self.camera.global_position[1] + self.camera.offset[1]) * zoom,
                    )

                    camera_offset_centered = (
                        camera_offset_node_position[0] + viewport_size[0] / 2.0,
                        camera_offset_node_position[1] + viewport_size[1] / 2.0,
                    )

                    render_texture = texture
                    if abs(zoom - 1.0) > 0.001:
                        target_w = max(1, int(texture.get_width() * zoom))
                        target_h = max(1, int(texture.get_height() * zoom))
                        scaled_key = (id(texture), target_w, target_h)
                        render_texture = scaled_texture_cache.get(scaled_key)
                        if render_texture is None:
                            render_texture = self.pygame.transform.scale(texture, (target_w, target_h))
                            scaled_texture_cache[scaled_key] = render_texture

                    if is_dim_layer:
                        dim_key = (id(render_texture), int(dim_factor * 1000))
                        dimmed_texture = dimmed_texture_cache.get(dim_key)
                        if dimmed_texture is None:
                            dimmed_texture = render_texture.copy()
                            mul = max(0, min(255, int(255 * dim_factor)))
                            dimmed_texture.fill((mul, mul, mul), special_flags=self.pygame.BLEND_RGB_MULT)
                            dimmed_texture_cache[dim_key] = dimmed_texture
                        render_texture = dimmed_texture

                    self.screen.blit(render_texture, camera_offset_centered)


    def create_node_structure(self, node, nodes_array=None):
        if nodes_array is None:
            nodes_array = []

        if isinstance(node, (Nodes.Sprite2D, Nodes.TileMap2D)):
            nodes_array.append(node)

        for child in getattr(node, '_children', []):
            self.create_node_structure(child, nodes_array)

        return nodes_array
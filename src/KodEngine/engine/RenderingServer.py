import pygame
from ..engine import Globals
from . import Nodes
from . import Resources
from .ErrorHandler import ErrorHandler
import math
import os

#rendering works by sorting nodes by z-index and rendering them 
class Renderer2D:
    def __init__(self, _configuration, _pygame, _screen, _debug_renderer=None) -> None:
        self.configuration = _configuration
        self.pygame = _pygame
        self.screen = _screen
        self.debug_renderer = _debug_renderer
        self._ui_font_cache = {}

    def is_inside_viewport(self, object, camera, project_settings):
        texture = object.image
        if texture is None:
            return False

        zoom = self._get_camera_zoom()
        cam_x, cam_y = self._get_camera_world_position_for_viewport(camera, project_settings, zoom)
        camera_center_x = cam_x - camera.offset[0]
        camera_center_y = cam_y - camera.offset[1]

        half_viewport_world_w = project_settings[0] / (2.0 * zoom)
        half_viewport_world_h = project_settings[1] / (2.0 * zoom)

        frustum_left = camera_center_x - half_viewport_world_w
        frustum_right = camera_center_x + half_viewport_world_w
        frustum_top = camera_center_y - half_viewport_world_h
        frustum_bottom = camera_center_y + half_viewport_world_h

        object_left = object.global_position[0]
        object_top = object.global_position[1]

        if hasattr(object, "offset"):
            object_left += object.offset[0]
            object_top += object.offset[1]
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
        cam_x, cam_y = self._get_camera_world_position_for_viewport(camera, project_settings, zoom)
        camera_center_x = cam_x - camera.offset[0]
        camera_center_y = cam_y - camera.offset[1]

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

    def render_ui_frame(self, ui_nodes, viewport_size=None, target_surface=None, source_size=None):
        if viewport_size is None:
            viewport_size = self._viewport_size()

        if not ui_nodes:
            return

        surface = target_surface if target_surface is not None else self.screen
        if surface is None:
            return

        if source_size is None:
            source_size = self.configuration.project_settings["window"].get(
                "internal_viewport_resolution",
                (1, 1)
            )

        ui_nodes = list(ui_nodes)
        ui_nodes.sort(
            key=lambda node: getattr(node, "z_index", 0)
        )

        scale_x, scale_y = self._ui_scale(
            source_size,
            viewport_size
        )

        for ui_node in ui_nodes:
            self.render_ui_node(
                ui_node,
                scale_x,
                scale_y,
                surface
            )

    def _scale_ui_rect(self, node, scale_x, scale_y):
        pos = getattr(
            node,
            "global_position",
            (0, 0)
        )

        size = getattr(
            node,
            "size",
            (0, 0)
        )

        x = int(pos[0] * scale_x)
        y = int(pos[1] * scale_y)

        w = int(size[0] * scale_x)
        h = int(size[1] * scale_y)

        return (
            x,
            y,
            w,
            h
        )

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

    def _collect_all_sprites(self, node, out_list):
        if isinstance(node, (Nodes.Sprite2D, Nodes.TileMap2D)):
            out_list.append(node)
        
        for child in getattr(node, "_children", []):
            self._collect_all_sprites(child, out_list)

    def _viewport_size(self):
        try:
            size = self.screen.get_size()
            if isinstance(size, (list, tuple)) and len(size) >= 2:
                return (int(size[0]), int(size[1]))
        except Exception:
            pass

        fallback = self.configuration.project_settings["window"].get("internal_viewport_resolution", (640, 360))
        return (int(fallback[0]), int(fallback[1]))

    def _ui_scale(self, source_size, viewport_size):
        internal_w, internal_h = source_size
        internal_w = max(1.0, float(internal_w))
        internal_h = max(1.0, float(internal_h))
        viewport_w = max(1.0, float(viewport_size[0]))
        viewport_h = max(1.0, float(viewport_size[1]))
        return (viewport_w / internal_w, viewport_h / internal_h)

    def _ui_font_path(self):
        return os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "editor", "assets", "fonts", "kod_default_font.otf")
        )


    def _render_ui_text(self, text, position, scale_y, surface, _font : str | None = "", _font_size=Globals.THEME_DEFAULTS.get("font_size", 16), color=(255, 255, 255), center=False):
        font_size = max(1, int(round(_font_size * scale_y)))
        try:
            font = pygame.font.Font(_font, font_size)
        except Exception as e:
            print(f"Error loading font: {e}")
            font = pygame.sysfont.SysFont(None, font_size)
        
        text_surface = font.render(str(text), True, color)
        text_rect = text_surface.get_rect()
        if center:
            text_rect.center = position
        else:
            text_rect.topleft = position
        surface.blit(text_surface, text_rect)

    def render_ui_node(self, node, scale_x, scale_y, surface):
        if isinstance(node, Nodes.Node2D) and not node.global_visible:
            return


        if isinstance(node, Nodes.ColorRect2D):
            rect_x, rect_y, rect_w, rect_h = self._scale_ui_rect(
                node,
                scale_x,
                scale_y
            )

            if rect_w <= 0 or rect_h <= 0:
                return

            color = getattr(
                node,
                "color",
                (255, 255, 255, 255)
            )

            s = self.pygame.Surface(
                (rect_w, rect_h),
                self.pygame.SRCALPHA
            )

            s.fill(color)

            surface.blit(
                s,
                (rect_x, rect_y)
            )

            return


        if isinstance(node, Nodes.Label):
            rect_x, rect_y, rect_w, rect_h = self._scale_ui_rect(
                node,
                scale_x,
                scale_y
            )

            color = getattr(
                node,
                "font_color",
                (255, 255, 255)
            )

            text = getattr(
                node,
                "text",
                ""
            )

            self._render_ui_text(
                text,
                (
                    rect_x + rect_w / 2.0,
                    rect_y + rect_h / 2.0
                ),
                scale_y,
                surface,
                _font=node.font.resource_path,
                _font_size=node.font_size,
                color=color,
                center=True
            )

            return


        if isinstance(node, Nodes.Button):
            rect_x, rect_y, rect_w, rect_h = self._scale_ui_rect(
                node,
                scale_x,
                scale_y
            )

            if rect_w <= 0 or rect_h <= 0:
                return

            if not getattr(
                node,
                "flat",
                False
            ):
                bg_color = getattr(
                    node,
                    "bg_color",
                    (100, 100, 100)
                )

                s = self.pygame.Surface(
                    (rect_w, rect_h),
                    self.pygame.SRCALPHA
                )

                s.fill(bg_color)

                surface.blit(
                    s,
                    (rect_x, rect_y)
                )

            self._render_ui_text(
                node.text,
                (
                    rect_x + rect_w / 2.0,
                    rect_y + rect_h / 2.0
                ),
                scale_y,
                surface,
                _font=node.font.resource_path,
                _font_size=node.font_size,
                color=node.font_color,
                center=True
            )

            return
        if isinstance(node, Nodes.TextureProgress):
            rect_x, rect_y, rect_w, rect_h = self._scale_ui_rect(
                node,
                scale_x,
                scale_y
            )

            if rect_w <= 0 or rect_h <= 0:
                return

            under_res = getattr(node, "_under_texture_resource", None) or getattr(node, "under_texture", None)
            fill_res = getattr(node, "_fill_texture_resource", None) or getattr(node, "fill_texture", None)

            under_surf = None
            fill_surf = None
            try:
                if under_res is not None:
                    under_surf = under_res.get_texture() if hasattr(under_res, "get_texture") else under_res
            except Exception:
                under_surf = None

            try:
                if fill_res is not None:
                    fill_surf = fill_res.get_texture() if hasattr(fill_res, "get_texture") else fill_res
            except Exception:
                fill_surf = None

            if under_surf is not None:
                try:
                    if under_surf.get_width() != rect_w or under_surf.get_height() != rect_h:
                        under_tex = self.pygame.transform.scale(under_surf, (rect_w, rect_h))
                    else:
                        under_tex = under_surf
                    surface.blit(under_tex, (rect_x, rect_y))
                except Exception:
                    s = self.pygame.Surface((rect_w, rect_h), self.pygame.SRCALPHA)
                    s.fill((60, 60, 60, 255))
                    surface.blit(s, (rect_x, rect_y))
            else:
                s = self.pygame.Surface((rect_w, rect_h), self.pygame.SRCALPHA)
                s.fill((60, 60, 60, 255))
                surface.blit(s, (rect_x, rect_y))

            try:
                v = float(getattr(node, "value", 0.0))
                minv = float(getattr(node, "min_value", 0.0))
                maxv = float(getattr(node, "max_value", 100.0))
            except Exception:
                v, minv, maxv = 0.0, 0.0, 100.0

            denom = maxv - minv if (maxv - minv) != 0 else 1.0
            ratio = max(0.0, min(1.0, (v - minv) / denom))
            fill_w = int(rect_w * ratio)

            if fill_w <= 0:
                return

            if fill_surf is not None:
                try:
                    if fill_surf.get_width() != rect_w or fill_surf.get_height() != rect_h:
                        scaled = self.pygame.transform.scale(fill_surf, (rect_w, rect_h))
                    else:
                        scaled = fill_surf

                    try:
                        fill_part = scaled.subsurface((0, 0, fill_w, rect_h)).copy()
                    except Exception:
                        fill_part = self.pygame.Surface((fill_w, rect_h), self.pygame.SRCALPHA)
                        fill_part.blit(scaled, (0, 0), (0, 0, fill_w, rect_h))

                    surface.blit(fill_part, (rect_x, rect_y))
                except Exception:
                    s2 = self.pygame.Surface((fill_w, rect_h), self.pygame.SRCALPHA)
                    s2.fill((0, 200, 0, 255))
                    surface.blit(s2, (rect_x, rect_y))
            else:
                s2 = self.pygame.Surface((fill_w, rect_h), self.pygame.SRCALPHA)
                s2.fill((0, 200, 0, 255))
                surface.blit(s2, (rect_x, rect_y))

            return

        if isinstance(node, Nodes.TextureRect2D):
            tex = node.image

            if tex is None:
                return

            rect_x, rect_y, rect_w, rect_h = self._scale_ui_rect(
                node,
                scale_x,
                scale_y
            )

            if rect_w <= 0 or rect_h <= 0:
                return

            if tex.get_width() != rect_w or tex.get_height() != rect_h:
                tex = self.pygame.transform.scale(
                    tex,
                    (
                        rect_w,
                        rect_h
                    )
                )

            surface.blit(
                tex,
                (
                    rect_x,
                    rect_y
                )
            )

    def _get_camera_world_position_for_viewport(self, camera, viewport_size, zoom=None):
        if zoom is None:
            zoom = self._get_camera_zoom()

        cam_x, cam_y = camera.global_position
        offset_x, offset_y = getattr(camera, "offset", (0, 0))

        center_x = cam_x - offset_x
        center_y = cam_y - offset_y

        half_viewport_world_w = viewport_size[0] / (2.0 * zoom)
        half_viewport_world_h = viewport_size[1] / (2.0 * zoom)

        limit_min = getattr(camera, "limit_min", (-1, -1))
        limit_max = getattr(camera, "limit_max", (-1, -1))

        min_x = float(limit_min[0]) if len(limit_min) > 0 else -1.0
        min_y = float(limit_min[1]) if len(limit_min) > 1 else -1.0
        max_x = float(limit_max[0]) if len(limit_max) > 0 else -1.0
        max_y = float(limit_max[1]) if len(limit_max) > 1 else -1.0

        has_min_x = min_x != -1
        has_min_y = min_y != -1
        has_max_x = max_x != -1
        has_max_y = max_y != -1

        min_center_x = min_x + half_viewport_world_w
        max_center_x = max_x - half_viewport_world_w
        min_center_y = min_y + half_viewport_world_h
        max_center_y = max_y - half_viewport_world_h

        if has_min_x and has_max_x and min_center_x > max_center_x:
            center_x = (min_center_x + max_center_x) / 2.0
        else:
            if has_min_x:
                center_x = max(center_x, min_center_x)
            if has_max_x:
                center_x = min(center_x, max_center_x)

        if has_min_y and has_max_y and min_center_y > max_center_y:
            center_y = (min_center_y + max_center_y) / 2.0
        else:
            if has_min_y:
                center_y = max(center_y, min_center_y)
            if has_max_y:
                center_y = min(center_y, max_center_y)

        return (center_x + offset_x, center_y + offset_y)

    def render_node(self, node):
        if isinstance(node, Nodes.Node2D) and not node.global_visible:
            return

        if isinstance(node, Nodes.TileMap2D):
            self.render_tilemap(node)
            return
        
        if isinstance(node, Nodes.YSort2D):
            renderables = []
            for child in getattr(node, "_children", []):
                self._collect_all_sprites(child, renderables)

            renderables.sort(key=lambda n: n.global_position[1])
            
            for r in renderables:
                self.render_node(r)
            return
        
        if isinstance(node, Nodes.ColorRect2D):
            viewport_size = self._viewport_size()
            cam_x, cam_y = self._get_camera_world_position_for_viewport(self.camera, viewport_size)
            zoom = self._get_camera_zoom()

            rect_x = (node.global_position[0] - cam_x + self.camera.offset[0]) * zoom + (viewport_size[0] / 2.0)
            rect_y = (node.global_position[1] - cam_y + self.camera.offset[1]) * zoom + (viewport_size[1] / 2.0)
            rect_w = max(1, int(getattr(node, "size", (0, 0))[0] * zoom))
            rect_h = max(1, int(getattr(node, "size", (0, 0))[1] * zoom))

            color = getattr(node, "color", (255, 255, 255, 255))
            if color is None or not isinstance(color, (tuple, list)):
                color = (255, 255, 255, 255)
            else:
                try:
                    color = tuple(int(c) for c in color)
                    if len(color) == 3:
                        color = (*color, 255)
                    elif len(color) != 4:
                        color = (255, 255, 255, 255)
                except (ValueError, TypeError):
                    color = (255, 255, 255, 255)

            s = self.pygame.Surface((rect_w, rect_h), self.pygame.SRCALPHA)
            s.fill(color)
            self.screen.blit(s, (int(rect_x), int(rect_y)))
            return
    
        if isinstance(node, Nodes.TextureRect2D):
            tex = node.image
            if tex is None:
                return

            viewport_size = self._viewport_size()

            # this performs frustum culling to improve performance but im not sure if its actually faster since i dont exactly know how sdl works and if the frustum check is more expensive than just rendering the texture
            if not self.is_inside_viewport(node, self.camera, viewport_size):
                return
            
        
            zoom = self._get_camera_zoom()
            cam_x, cam_y = self._get_camera_world_position_for_viewport(self.camera, viewport_size, zoom)

            camera_offset_node_position = (
                (node.global_position[0] - cam_x + self.camera.offset[0]) * zoom,
                (node.global_position[1] - cam_y + self.camera.offset[1]) * zoom,
            )

       
            camera_offset_centered = (
                camera_offset_node_position[0] + viewport_size[0] / 2.0,
                camera_offset_node_position[1] + viewport_size[1] / 2.0
            )



            camera_space_translation = (
                camera_offset_centered[0] + 0.0 * zoom,
                camera_offset_centered[1] + 0.0 * zoom,
            )

            if abs(zoom - 1.0) > 0.001:
                target_w = max(1, int(tex.get_width() * zoom))
                target_h = max(1, int(tex.get_height() * zoom))
                tex = self.pygame.transform.scale(tex, (target_w, target_h))

            self.screen.blit(tex, camera_space_translation)

        if isinstance(node, Nodes.Sprite2D):
            tex = node.image
            if tex is None:
                return

            viewport_size = self._viewport_size()

            # this performs frustum culling to improve performance but im not sure if its actually faster since i dont exactly know how sdl works and if the frustum check is more expensive than just rendering the texture
            if not self.is_inside_viewport(node, self.camera, viewport_size):
                return
            
        
            zoom = self._get_camera_zoom()
            cam_x, cam_y = self._get_camera_world_position_for_viewport(self.camera, viewport_size, zoom)

            camera_offset_node_position = (
                (node.global_position[0] - cam_x + self.camera.offset[0]) * zoom,
                (node.global_position[1] - cam_y + self.camera.offset[1]) * zoom,
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
        chunked_layers = getattr(node, "_chunked_tile_data", {})
        chunk_size = getattr(node, "chunk_size", 16)
        
        if tileset is None or not chunked_layers:
            return

        zoom = self._get_camera_zoom()
        viewport_size = self._viewport_size()
        tw, th = tileset.tile_size if hasattr(tileset, "tile_size") else (16, 16)
        
        cam_x, cam_y = self._get_camera_world_position_for_viewport(self.camera, viewport_size, zoom)
        half_w = viewport_size[0] / (2.0 * zoom)
        half_h = viewport_size[1] / (2.0 * zoom)
     
        view_left = cam_x - half_w - node.global_position[0]
        view_right = cam_x + half_w - node.global_position[0]
        view_top = cam_y - half_h - node.global_position[1]
        view_bottom = cam_y + half_h - node.global_position[1]

        chunk_pixel_w = tw * chunk_size
        chunk_pixel_h = th * chunk_size
        
        min_cx = int(math.floor(view_left / chunk_pixel_w))
        max_cx = int(math.floor(view_right / chunk_pixel_w))
        min_cy = int(math.floor(view_top / chunk_pixel_h))
        max_cy = int(math.floor(view_bottom / chunk_pixel_h))

        active_layer = getattr(node, "_editor_active_paint_layer", None)
        active_layer_index = int(active_layer) if isinstance(active_layer, int) else None
        selection_settings = self.configuration.editor_settings.get("selection", {})
        selected_node_id = selection_settings.get("selected_node_id")
        is_selected_tilemap = (selected_node_id == id(node))
        dim_non_active = ErrorHandler.is_editor_mode() and is_selected_tilemap and active_layer_index is not None
        dim_factor = 0.45

        scaled_texture_cache = {}
        dimmed_texture_cache = {}

        node_x, node_y = node.global_position

        for layer_index in sorted(chunked_layers.keys()):
            layer_chunks = chunked_layers[layer_index]
            is_dim_layer = (dim_non_active and int(layer_index) != active_layer_index)

            for cx in range(min_cx, max_cx + 1):
                for cy in range(min_cy, max_cy + 1):
                    chunk_data = layer_chunks.get((cx, cy))
                    if not chunk_data:
                        continue
                    
                    for i, tile_id in enumerate(chunk_data):
                        if tile_id < 0:
                            continue

                        tx = cx * chunk_size + (i % chunk_size)
                        ty = cy * chunk_size + (i // chunk_size)
                        
                        texture = tileset.get_tile_surface(tile_id)
                        if not texture:
                            continue

                        world_tx, world_ty = node.tile_to_world((tx, ty))
                        
                        screen_x = (node_x + world_tx - cam_x + self.camera.offset[0]) * zoom + (viewport_size[0] / 2.0)
                        screen_y = (node_y + world_ty - cam_y + self.camera.offset[1]) * zoom + (viewport_size[1] / 2.0)

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

                        self.screen.blit(render_texture, (int(screen_x), int(screen_y)))


    def create_node_structure(self, node, nodes_array=None):
        if nodes_array is None:
            nodes_array = []

        if isinstance(node, (Nodes.Sprite2D, Nodes.TileMap2D)):
            nodes_array.append(node)

        for child in getattr(node, '_children', []):
            self.create_node_structure(child, nodes_array)

        return nodes_array
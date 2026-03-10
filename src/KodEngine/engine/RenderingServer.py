from . import Nodes

#render works by sorting nodes by z-index and rendering them 
class Renderer:
    def __init__(self, _configuration, _pygame, _screen, _debug_renderer=None) -> None:
        self.configuration = _configuration
        self.pygame = _pygame
        self.screen = _screen
        self.debug_renderer = _debug_renderer

    #TODO: precompute nodes into buckets and pass the buckets to each server (Rendering, Physics) so that we dont loop through everything every frame.
    def render_frame(self, scene, _camera):
        self.camera = _camera
        self.screen.fill(self.configuration.editor_settings["default_background_color"])
        
        if scene != None:
            nodes = self.create_node_structure(scene.root)
            nodes.sort(key=lambda node: (node.z_index))
            
            for sprite in nodes:
                self.render_node(sprite)

        if self.debug_renderer is not None:
            self.debug_renderer.render(self.screen, self.pygame, self.camera)
        
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

    def render_node(self, node):
        #only render nodes that inherit from Sprite2D
        if isinstance(node, Nodes.Sprite2D):
            tex = node.image
            if tex is None:
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


    def create_node_structure(self, node, nodes_array=None):
        if nodes_array is None:
            nodes_array = []

        if isinstance(node, Nodes.Sprite2D):
            nodes_array.append(node)

        for child in getattr(node, '_children', []):
            self.create_node_structure(child, nodes_array)

        return nodes_array
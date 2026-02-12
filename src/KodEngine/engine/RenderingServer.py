from . import Nodes

#render works by sorting nodes by z-index and rendnering them 
class Renderer:
    def __init__(self, _configuration, _pygame, _screen) -> None:
        self.configuration = _configuration
        self.pygame = _pygame
        self.screen = _screen

    #TODO: precompute nodes into buckets and pass the buckets to each server (Rendering, Physics) so that we dont loop through everything every frame.
    def render_frame(self, scene, _camera):
        self.camera = _camera
        self.screen.fill(self.configuration.editor_settings["default_background_color"])
        
        if scene != None:
            nodes = self.create_node_structure(scene.root)
            nodes.sort(key=lambda node: (node.z_index))
            
            for sprite in nodes:
                self.render_node(sprite)
        
        self.pygame.display.flip()

    #rendering accounts for camera transformation and offset
    
    def render_node(self, node):
        #only render nodes that inherit from Sprite2D
        if isinstance(node, Nodes.Sprite2D):
            tex = node.image
            if tex is None:
                return

            camera_offset_node_position = (
                node.global_position[0] - self.camera.global_position[0] + self.camera.offset[0],
                node.global_position[1] - self.camera.global_position[1] + self.camera.offset[1]
            )

            camera_offset_centered = (
                camera_offset_node_position[0] + self.configuration.project_settings["window"]["internal_viewport_resolution"][0] / 2.0,
                camera_offset_node_position[1] + self.configuration.project_settings["window"]["internal_viewport_resolution"][1] / 2.0
            )

            tex_width, tex_height = tex.get_size()
            blit_position = (
                camera_offset_centered[0] - tex_width / 2.0,
                camera_offset_centered[1] - tex_height / 2.0
            )

            self.screen.blit(tex, blit_position)


    def create_node_structure(self, node, nodes_array=None):
        if nodes_array is None:
            nodes_array = []

        if isinstance(node, Nodes.Sprite2D):
            nodes_array.append(node)

        for child in getattr(node, '_children', []):
            self.create_node_structure(child, nodes_array)

        return nodes_array
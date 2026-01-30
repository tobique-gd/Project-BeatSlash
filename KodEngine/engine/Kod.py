import pygame

import KodEngine.engine.RenderingServer as RenderingServer
import KodEngine.engine.Nodes as Nodes
import KodEngine.engine.Scenes as Scenes


class Settings:
    def __init__(self) -> None:
        self.window_settings = {
            "viewport_resolution": (1280, 720),
            "internal_viewport_resolution": (640, 360)
        }
        self.runtime_settings = {
            "FPS": 60
        }
        self.editor_settings = {
            "editor_resolution": (1920, 1080),
            "default_background_color": (50, 50, 50)
        }


class App:
    def __init__(self, configuration: Settings, editor_mode = False):
        pygame.init()

        self.internal_resolution = configuration.window_settings["internal_viewport_resolution"]
        self.resolution = configuration.window_settings["viewport_resolution"]
        self.FPS = configuration.runtime_settings["FPS"]

        if editor_mode:
            self.screen = pygame.display.set_mode(self.internal_resolution, pygame.HIDDEN)
        else:
            self.screen = pygame.display.set_mode(self.resolution, pygame.RESIZABLE, vsync=1)
        

        self.internal_surface = pygame.Surface(self.internal_resolution).convert_alpha()
        self.scaled_surface = pygame.transform.scale(self.internal_surface, self.resolution)

        self.clock = pygame.time.Clock()
        self.renderer = RenderingServer.Renderer(configuration, pygame, self.internal_surface)

        self.running = False
        self.current_scene = None

        self.fallback_camera = Nodes.Camera2D()
        self.current_camera = None

    def handle_resize(self, size):
        self.resolution = size
        self.screen = pygame.display.set_mode(self.resolution, pygame.RESIZABLE, vsync=1)
        self.scaled_surface = pygame.transform.scale(self.internal_surface, self.resolution)

    def set_scene(self, scene: Scenes.Scene):
        self.current_scene = scene
        if self.current_scene:
            self.current_scene._ready()

    def set_camera(self, camera: Nodes.Camera2D):
        self.current_camera = camera

    def find_camera_in_scene(self, node):
        if isinstance(node, Nodes.Camera2D):
            return node

        for child in getattr(node, "children", []):
            cam = self.find_camera_in_scene(child)
            if cam:
                return cam

        return None

    def resolve_camera(self):
        if self.current_camera:
            return self.current_camera

        if self.current_scene:
            cam = self.find_camera_in_scene(self.current_scene.root)
            if cam:
                return cam

        return self.fallback_camera

    def run(self):
        if not self.screen:
            return
        
        self.running = True
        last_frame_time = pygame.time.get_ticks()

        while self.running:
            now = pygame.time.get_ticks()
            delta = (now - last_frame_time) / 1000.0
            last_frame_time = now

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif event.type == pygame.VIDEORESIZE:
                    self.handle_resize(event.size)

                if self.current_scene:
                    self.current_scene._input(event)

            if self.current_scene:
                self.current_scene._process(delta)

            camera = self.resolve_camera()
            self.renderer.render_frame(self.current_scene, camera)

            self.scaled_surface = pygame.transform.scale(self.internal_surface, self.resolution)
            self.screen.blit(self.scaled_surface, (0, 0))

            self.clock.tick(self.FPS)

    def run_in_editor(self, editor_camera):
        if not self.screen:
            return

        self.renderer.render_frame(self.current_scene, editor_camera)

        self.scaled_surface = pygame.transform.scale(self.internal_surface, self.resolution)
        self.screen.blit(self.scaled_surface, (0, 0))

        self.clock.tick(self.FPS)
    
    def kill(self):
        pygame.quit()
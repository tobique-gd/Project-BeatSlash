import pygame
import math
import platform
from typing import Any



from . import PhysicsServer
from . import RenderingServer
from . import Nodes
from . import Scenes
from . import ErrorHandler


class Settings:
    def __init__(self) -> None:
        self.project_settings = {
            "file_management" : {
                "project_directory" : "/",
            },

            "window" : {
                "viewport_resolution" : (1920, 1080),
                "internal_viewport_resolution" : (480, 270)
            },
            "physics" : {
                "physics_substeps" : 4
            },
            "runtime" : {
                "main_scene_path" : "src/BeatSlash/scenes/BeatSlashWorld.kscn",
                "FPS" : 60
            }

        }

        self.editor_settings = {}

class App:
    def __init__(self, _configuration: Settings, editor_mode = False):
        pygame.init()

        self.configuration = _configuration
        self.internal_resolution = self.configuration.project_settings["window"]["internal_viewport_resolution"]
        self.base_internal_resolution = (
            int(self.internal_resolution[0]),
            int(self.internal_resolution[1]),
        )
        self.resolution = self.configuration.project_settings["window"]["viewport_resolution"]
        self.FPS = self.configuration.project_settings["runtime"]["FPS"]

        if editor_mode:
            self.screen = pygame.display.set_mode(self.internal_resolution, pygame.HIDDEN)
        else:
            self.screen = self._create_runtime_window(self.resolution)
        

        self.internal_surface = pygame.Surface(self.internal_resolution).convert_alpha()
        self.scaled_surface = pygame.transform.scale(self.internal_surface, self.resolution)

        self.clock = pygame.time.Clock()
        self.debug_renderer: Any | None = None
        self.renderer = RenderingServer.Renderer2D(
            self.configuration,
            pygame,
            self.internal_surface,
            self.debug_renderer,
        )
        self.physics_solver = PhysicsServer.PhysicsSolver2D(
            self.configuration
        )

        self.running = False
        self.current_scene = None

        self.fallback_camera = Nodes.Camera2D()
        self.current_camera = None

    #handling resizing of window since pygame doesnt do it automatically
    def handle_resize(self, size):
        width = max(1, int(size[0]))
        height = max(1, int(size[1]))

        self.resolution = (width, height)
        self.configuration.project_settings["window"]["viewport_resolution"] = self.resolution

        current_surface = pygame.display.get_surface()
        if current_surface is not None:
            self.screen = current_surface

    def _create_runtime_window(self, resolution):
        # pygame-ce can crash on macOS when vsync is requested during display mode changes.
        if platform.system() == "Darwin":
            try:
                return pygame.display.set_mode(resolution, pygame.RESIZABLE, vsync=1)
            except:
                return pygame.display.set_mode(resolution, pygame.RESIZABLE)
            
        try:
            return pygame.display.set_mode(resolution, pygame.RESIZABLE, vsync=1)
        except TypeError:
            return pygame.display.set_mode(resolution, pygame.RESIZABLE)

    def _present_internal_surface(self):
        internal_w, internal_h = self.base_internal_resolution
        output_w, output_h = self.resolution

        if internal_w <= 0 or internal_h <= 0 or output_w <= 0 or output_h <= 0:
            return
        
        scale_x = output_w / float(internal_w)
        scale_y = output_h / float(internal_h)
        integer_scale = max(1, int(math.ceil(max(scale_x, scale_y))))

        target_w = internal_w * integer_scale
        target_h = internal_h * integer_scale

        offset_x = (output_w - target_w) // 2
        offset_y = (output_h - target_h) // 2

        self.scaled_surface = pygame.transform.scale(self.internal_surface, (target_w, target_h))
        self.screen.blit(self.scaled_surface, (offset_x, offset_y))
        

    def set_scene(self, scene):
        if self.current_scene and getattr(self.current_scene, "root", None):
            try:
                self.current_scene.root.on_exit()
            except Exception:
                pass

        self.current_scene = scene

        if self.current_scene and getattr(self.current_scene, "root", None):
            try:
                self.current_scene.root._on_enter()
            except Exception:
                pass

    def set_camera(self, camera: Nodes.Camera2D):
        self.current_camera = camera

    def find_camera_in_scene(self, node):
        if isinstance(node, Nodes.Camera2D) and node.current == True:
            return node

        for child in getattr(node, "_children", []):
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

    def resolve_editor_events(self, events):
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.VIDEORESIZE:
                self.handle_resize(event.size)

            if self.current_scene:
                self.current_scene._input(event)

    def calculate_delta(self, last_frame_time):
        now = pygame.time.get_ticks()
        delta = (now - last_frame_time) / 1000.0
        return delta

    def distribute_node_buckets(self):
        buckets = {
            "rendering": [],
            "physics": [],
        }

        if not self.current_scene or not getattr(self.current_scene, "root", None):
            return buckets

        rendering_types = (Nodes.Sprite2D, Nodes.AnimatedSprite2D, Nodes.TileMap2D)
        physics_types = (Nodes.DynamicBody2D, Nodes.KinematicBody2D, Nodes.StaticBody2D)

        def traverse(node, inside_ysort=False):
            is_ysort = isinstance(node, Nodes.YSort2D)

            if isinstance(node, physics_types):
                buckets["physics"].append(node)

            if is_ysort:
                buckets["rendering"].append(node)
            elif isinstance(node, rendering_types) and not inside_ysort:
                buckets["rendering"].append(node)

            child_inside_ysort = inside_ysort or is_ysort
            for child in getattr(node, "_children", []):
                traverse(child, child_inside_ysort)

        traverse(self.current_scene.root)
        return buckets

    def run(self):
        if not self.screen:
            ErrorHandler.throw_error("No screen set. Stopping running.")
            return
        
        if not self.current_scene:
            ErrorHandler.throw_error("No scene set. Stopping running.")
            return
        
        self.internal_resolution = self.base_internal_resolution
        self.configuration.project_settings["window"]["internal_viewport_resolution"] = self.internal_resolution
        self.internal_surface = pygame.Surface(self.internal_resolution).convert_alpha()
        self.renderer.screen = self.internal_surface
        
        
        self.current_scene._ready()
        self.running = True
        last_frame_time = pygame.time.get_ticks()
        self.resolution = self.screen.get_size()
        

        while self.running:
            delta = self.calculate_delta(last_frame_time)
            last_frame_time = pygame.time.get_ticks()

            self.resolve_editor_events(pygame.event.get())
            self.current_scene._process(delta)

            self.node_buckets = self.distribute_node_buckets()

            camera = self.resolve_camera()
            
            self.physics_solver.physics_process(self.node_buckets["physics"], delta)
            self.renderer.render_frame(self.current_scene, camera, self.node_buckets["rendering"])
            self._present_internal_surface()
            pygame.display.flip()

            self.clock.tick(self.FPS)
    


    def kill(self):
        pygame.quit()
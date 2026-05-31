import os
import warnings
import math
import platform
from typing import Any

warnings.filterwarnings(
    "ignore",
    message=r"pkg_resources is deprecated as an API.*",
    category=UserWarning,
    module=r"pygame\.pkgdata",
)

import pygame

from . import PhysicsServer
from . import RenderingServer
from . import Nodes
from . import Scenes
from . import ErrorHandler
from . import Globals


class Settings:
    """Default project and editor configuration container."""

    def __init__(self) -> None:
        """Populate default runtime and project settings."""
        project_directory = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "BeatSlash")
        )

        self.project_settings = {
            "project" : {
                "name" : "BeatSlash",
                "main_scene_path" : "scenes/main_menu/main_menu.kscn"
            },

            "file_management" : {
                "project_directory" : project_directory,
            },

            "window" : {
                "viewport_resolution" : (1920, 1080),
                "internal_viewport_resolution" : (480, 270)
            },
            "physics" : {
                "physics_substeps" : 4
            },
            "runtime" : {
                "FPS" : 240
            },
            "debug": {
                "default_background_color": (50, 50, 50),
                "show_collision_shapes_runtime": False,
            }

        }

        self.editor_settings = {}

class App:
    """Main application runner for the engine runtime and editor."""

    def __init__(self, _configuration: Settings, editor_mode = False):
        """Create the application and initialize pygame.

        Parameters
        ----------
        _configuration:
            Project settings container.
        editor_mode:
            When ``True``, the app runs without a visible runtime window.
        """
        pygame.init()
        pygame.font.init()

        self.configuration = _configuration
        self.internal_resolution = self.configuration.project_settings["window"]["internal_viewport_resolution"]
        self.base_internal_resolution = (
            int(self.internal_resolution[0]),
            int(self.internal_resolution[1]),
        )
        self.resolution = self.configuration.project_settings["window"]["viewport_resolution"]
        self.FPS = self.configuration.project_settings["runtime"]["FPS"]
        self.editor_mode = editor_mode

        if editor_mode:
            self.screen = pygame.display.set_mode(self.internal_resolution, pygame.HIDDEN)
        else:
            self.screen = self._create_runtime_window(self.resolution)

        if self.screen is not None:
            self.handle_resize(self.screen.get_size(), persist_project_resolution=not editor_mode)
        
        pygame.display.set_caption(self.configuration.project_settings["project"]["name"])
        self.internal_surface = pygame.Surface(self.internal_resolution).convert_alpha()
        self.scaled_surface = pygame.transform.scale(self.internal_surface, self.resolution)

        self.clock = pygame.time.Clock()
        self.debug_renderer: Any | None = None
        self.time_scale = 1.0
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
        self._shutdown_requested = False
        self.current_scene = None
        Globals.APP = self

        self.fallback_camera = Nodes.Camera2D()
        self.current_camera = None

    #handling resizing of window since pygame doesnt do it automatically
    def handle_resize(self, size, persist_project_resolution=True):
        """Update the runtime viewport and optionally persist it to settings.

        Parameters
        ----------
        size:
            New window size.
        persist_project_resolution:
            When ``True``, store the updated size in project settings.
        """
        width = max(1, int(size[0]))
        height = max(1, int(size[1]))

        self.resolution = (width, height)
        if persist_project_resolution:
            self.configuration.project_settings["window"]["viewport_resolution"] = self.resolution

        current_surface = pygame.display.get_surface()
        if current_surface is not None:
            self.screen = current_surface

    def _create_runtime_window(self, resolution):
        """Create the runtime window with platform-specific vsync handling."""
        # macOS vsync causes FPS throttling when window loses focus (dock visibility).
        # Use clock.tick() instead for reliable frame limiting independent of focus.
        if platform.system() == "Darwin":
            return pygame.display.set_mode(resolution, pygame.RESIZABLE)
            
        try:
            return pygame.display.set_mode(resolution, pygame.RESIZABLE, vsync=1)
        except TypeError:
            return pygame.display.set_mode(resolution, pygame.RESIZABLE)

    def _present_internal_surface(self):
        """Scale the internal surface to the output window and present it."""
        internal_w, internal_h, integer_scale, offset_x, offset_y, target_w, target_h = self._calculate_present_transform()
        if internal_w <= 0 or internal_h <= 0:
            return

        self.scaled_surface = pygame.transform.scale(self.internal_surface, (target_w, target_h))
        self.screen.blit(self.scaled_surface, (offset_x, offset_y))

    def _calculate_present_transform(self):
        """Compute integer scaling and centering for the editor presentation.

        Returns
        -------
        tuple[int, int, int, int, int, int, int]
            Internal size, integer scale, offsets, and target size.
        """
        internal_w, internal_h = self.base_internal_resolution
        output_w, output_h = self.screen.get_size() if self.screen else self.resolution

        if internal_w <= 0 or internal_h <= 0 or output_w <= 0 or output_h <= 0:
            return (0, 0, 1, 0, 0, 0, 0)

        scale_x = output_w / float(internal_w)
        scale_y = output_h / float(internal_h)
        integer_scale = max(1, int(math.ceil(max(scale_x, scale_y))))

        target_w = internal_w * integer_scale
        target_h = internal_h * integer_scale

        offset_x = (output_w - target_w) // 2
        offset_y = (output_h - target_h) // 2
        return (internal_w, internal_h, integer_scale, offset_x, offset_y, target_w, target_h)

    def _window_to_internal_pos(self, pos):
        """Convert a window-space mouse position into internal coordinates."""
        internal_w, internal_h, integer_scale, offset_x, offset_y, _, _ = self._calculate_present_transform()
        if internal_w <= 0 or internal_h <= 0:
            return pos

        x = (float(pos[0]) - float(offset_x)) / float(integer_scale)
        y = (float(pos[1]) - float(offset_y)) / float(integer_scale)
        return (x, y)

    def _calculate_cover_transform(self, output_w, output_h):
        """Compute cover scaling for runtime presentation.

        Returns
        -------
        tuple[float, float, int, int, int, int]
            Scale factors, offsets, and target size.
        """
        internal_w, internal_h = self.internal_resolution
        if internal_w <= 0 or internal_h <= 0 or output_w <= 0 or output_h <= 0:
            return (1.0, 1.0, 0, 0, output_w, output_h)

        scale = max(output_w / float(internal_w), output_h / float(internal_h))
        target_w = int(round(internal_w * scale))
        target_h = int(round(internal_h * scale))
        offset_x = (output_w - target_w) // 2
        offset_y = (output_h - target_h) // 2
        return (scale, scale, offset_x, offset_y, target_w, target_h)

    def _normalize_event_to_internal_space(self, event):
        """Map mouse events from window space into internal render space."""
        if event.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            return event

        if not hasattr(event, "dict"):
            return event

        event_data = dict(event.dict)
        if "pos" not in event_data:
            return event

        if self.editor_mode:
            _, _, integer_scale, _, _, _, _ = self._calculate_present_transform()
            event_data["pos"] = self._window_to_internal_pos(event_data["pos"])

            if "rel" in event_data and integer_scale > 0:
                event_data["rel"] = (
                    float(event_data["rel"][0]) / float(integer_scale),
                    float(event_data["rel"][1]) / float(integer_scale),
                )
        else:
            output_w, output_h = self.screen.get_size() if self.screen else self.resolution
            internal_w, internal_h = self.internal_resolution
            scale_x, scale_y, offset_x, offset_y, _, _ = self._calculate_cover_transform(output_w, output_h)

            event_data["pos"] = (
                (float(event_data["pos"][0]) - float(offset_x)) / float(scale_x),
                (float(event_data["pos"][1]) - float(offset_y)) / float(scale_y),
            )

            if "rel" in event_data and scale_x > 0 and scale_y > 0:
                event_data["rel"] = (
                    float(event_data["rel"][0]) / float(scale_x),
                    float(event_data["rel"][1]) / float(scale_y),
                )

        return pygame.event.Event(event.type, event_data)
        

    def set_scene(self, scene):
        """Swap the active scene and run enter/ready hooks as needed."""
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
            try:
                if not self.editor_mode:
                    self.current_scene._ready()

            except Exception:
                pass

    def set_camera(self, camera: Nodes.Camera2D):
        """Set the active camera used for rendering."""
        self.current_camera = camera

    def find_camera_in_scene(self, node):
        """Recursively search a node tree for the active camera."""
        if isinstance(node, Nodes.Camera2D) and node.current == True:
            return node

        for child in getattr(node, "_children", []):
            cam = self.find_camera_in_scene(child)
            if cam:
                return cam

        return None

    def resolve_camera(self):
        """Return the active camera or the fallback camera."""
        if self.current_camera:
            return self.current_camera

        if self.current_scene:
            cam = self.find_camera_in_scene(self.current_scene.root)
            if cam:
                return cam

        return self.fallback_camera

    def resolve_editor_events(self, events):
        """Handle editor-level events and forward them to the current scene."""
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.VIDEORESIZE:
                self.handle_resize(event.size)

            if self.current_scene:
                scene_event = self._normalize_event_to_internal_space(event)
                self.current_scene._input(scene_event)

    def calculate_delta(self, last_frame_time):
        """Compute frame delta time from the previous tick timestamp."""
        now = pygame.time.get_ticks()
        delta = (now - last_frame_time) / 1000.0
        return delta * float(self.time_scale)

    def distribute_node_buckets(self):
        """Split the current scene into rendering, physics, and UI buckets.

        Returns
        -------
        dict[str, list]
            Node buckets keyed by ``rendering``, ``physics``, and ``ui``.
        """
        buckets = {
            "rendering": [],
            "physics": [],
            "ui": []
        }

        if not self.current_scene or not getattr(self.current_scene, "root", None):
            return buckets

        rendering_types = (Nodes.Sprite2D, Nodes.AnimatedSprite2D, Nodes.TileMap2D)
        physics_types = (Nodes.CollisionObject2D)
        ui_types = (Nodes.Label, Nodes.Button, Nodes.ColorRect2D, Nodes.TextureRect2D, Nodes.TextureProgress)

        def traverse(node, inside_ysort=False):
            is_ysort = isinstance(node, Nodes.YSort2D)

            if isinstance(node, ui_types):
                buckets["ui"].append(node)

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
        """Run the main application loop until the app is stopped."""
        if not self.screen or not self.current_scene:
            return

        self.current_scene._process_ui(self.internal_resolution)
        self.running = True
        last_frame_time = pygame.time.get_ticks()

        while self.running:
            now = pygame.time.get_ticks()
            delta = (now - last_frame_time) / 1000.0
            last_frame_time = now
            scaled_delta = delta * float(self.time_scale)

            self.current_scene._process_ui(self.internal_resolution)
            self.resolve_editor_events(pygame.event.get())

            self.current_scene._process(scaled_delta)
            self.node_buckets = self.distribute_node_buckets()
            camera = self.resolve_camera()

            self.physics_solver.physics_process(
                self.node_buckets["physics"],
                scaled_delta
            )

            self.renderer.render_frame(
                self.current_scene,
                camera,
                self.node_buckets["rendering"],
                self.node_buckets["physics"]
            )

            viewport_size = self.configuration.project_settings["window"]["viewport_resolution"] 
            output_w, output_h = int(viewport_size[0]), int(viewport_size[1])

            if self.scaled_surface is None or self.scaled_surface.get_size() != viewport_size:
                self.scaled_surface = pygame.Surface(viewport_size, pygame.SRCALPHA).convert_alpha()

            self.scaled_surface.fill((0, 0, 0, 255))
            scale_x, scale_y, offset_x, offset_y, target_w, target_h = self._calculate_cover_transform(output_w, output_h)
            if target_w > 0 and target_h > 0:
                scaled_internal = pygame.transform.scale(self.internal_surface, (target_w, target_h))
                self.scaled_surface.blit(scaled_internal, (offset_x, offset_y))

            if self.current_scene is not None:
                self.current_scene._process_ui(self.internal_resolution)

            self.renderer.render_ui_frame(
                self.node_buckets["ui"],
                viewport_size=viewport_size,
                target_surface=self.scaled_surface,
                source_size=self.internal_resolution
            )

            self.screen.blit(self.scaled_surface, (0, 0))
            pygame.display.flip()

        if self._shutdown_requested:
            pygame.quit()
                


    def kill(self):
        """Request shutdown of the main application loop."""
        self.running = False
        self._shutdown_requested = True
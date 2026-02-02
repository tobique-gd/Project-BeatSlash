import pygame

class SpriteAnimation:

    def __init__(self, name, spritesheet, frame_size: tuple[int,int], frames: int, _loop: bool, fps: int = 12):
        self.frames_surfaces = []
        self.frames_local_rects = []

        self.name = name
        self.spritesheet_path = None

        if isinstance(spritesheet, str):
            self.spritesheet_path = spritesheet
            if pygame is not None:
                try:
                    spritesheet_surface = pygame.image.load(spritesheet).convert_alpha()
                except Exception:
                    spritesheet_surface = None
            else:
                spritesheet_surface = None
        else:
            spritesheet_surface = spritesheet

        if spritesheet_surface is not None:
            for i in range(frames):
                rect = pygame.Rect(
                    (i * frame_size[0]) % spritesheet_surface.get_width(),
                    ((i * frame_size[0]) // spritesheet_surface.get_width()) * frame_size[1],
                    *frame_size
                )
                surface = spritesheet_surface.subsurface(rect).copy()
                self.frames_surfaces.append(surface)

                w, h = surface.get_size()
                self.frames_local_rects.append(((-w / 2, -h / 2), (w, h)))
        else:
            self.frames_surfaces = []
            self.frames_local_rects = []

        self.spritesheet = spritesheet_surface
        self.frame_size = frame_size
        self.frames = frames
        self.fps = fps

        self.current_frame = 0
        self.time_accumulator = 0.0
        self.loop = _loop
        self.finished = False

    def reload(self):
        if not self.frames_surfaces and self.spritesheet_path and pygame:
            try:
                spritesheet_surface = pygame.image.load(self.spritesheet_path).convert_alpha()
                self.spritesheet = spritesheet_surface
                self.frames_surfaces = []
                self.frames_local_rects = []
                
                for i in range(self.frames):
                    rect = pygame.Rect(
                        (i * self.frame_size[0]) % spritesheet_surface.get_width(),
                        ((i * self.frame_size[0]) // spritesheet_surface.get_width()) * self.frame_size[1],
                        *self.frame_size
                    )
                    surface = spritesheet_surface.subsurface(rect).copy()
                    self.frames_surfaces.append(surface)

                    w, h = surface.get_size()
                    self.frames_local_rects.append(((-w / 2, -h / 2), (w, h)))
            except Exception:
                pass


    def update(self, delta: float):
        if self.finished:
            return

        self.time_accumulator += delta
        frame_time = 1.0 / self.fps

        while self.time_accumulator >= frame_time:
            self.current_frame += 1
            self.time_accumulator -= frame_time

            if self.current_frame >= self.frames:
                if self.loop:
                    self.current_frame = 0
                else:
                    self.current_frame = self.frames - 1
                    self.finished = True
                    break
    
    def editor_update(self, delta):
        if self.finished:
            return

        self.time_accumulator += delta
        frame_time = 1.0 / self.fps

        while self.time_accumulator >= frame_time:
            self.current_frame += 1
            self.time_accumulator -= frame_time

            if self.current_frame >= self.frames:
                if self.loop:
                    self.current_frame = 0
                else:
                    self.current_frame = self.frames - 1
                    self.finished = True
                    break

    def get_current_frame_rect(self) -> pygame.Rect:
        if not self.spritesheet:
            return pygame.Rect(10, 10, 50, 50)

        frame_x = (self.current_frame * self.frame_size[0]) % self.spritesheet.get_width()
        frame_y = ((self.current_frame * self.frame_size[0]) // self.spritesheet.get_width()) * self.frame_size[1]
        return pygame.Rect(frame_x, frame_y, self.frame_size[0], self.frame_size[1])

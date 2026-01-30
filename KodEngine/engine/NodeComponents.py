import pygame

class SpriteAnimation:
    
    def __init__(self, name, spritesheet: pygame.Surface, frame_size: tuple[int,int], frames: int, _loop: bool, fps: int = 12):
        self.frames_surfaces = []
        self.frames_local_rects = []

        for i in range(frames):
            rect = pygame.Rect(
                (i * frame_size[0]) % spritesheet.get_width(),
                ((i * frame_size[0]) // spritesheet.get_width()) * frame_size[1],
                *frame_size
            )
            surface = spritesheet.subsurface(rect).copy()
            self.frames_surfaces.append(surface)

            w, h = surface.get_size()
            self.frames_local_rects.append(((-w / 2, -h / 2), (w, h)))

            
        self.name = name
        self.spritesheet = spritesheet
        self.frame_size = frame_size
        self.frames = frames
        self.fps = fps

        self.current_frame = 0
        self.time_accumulator = 0.0
        self.loop = _loop
        self.finished = False

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

    def get_current_frame_rect(self) -> pygame.Rect:
        frame_x = (self.current_frame * self.frame_size[0]) % self.spritesheet.get_width()
        frame_y = ((self.current_frame * self.frame_size[0]) // self.spritesheet.get_width()) * self.frame_size[1]
        return pygame.Rect(frame_x, frame_y, self.frame_size[0], self.frame_size[1])

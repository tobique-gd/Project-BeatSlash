import math

def normalized(vector: tuple[float, float]):
    x,y = vector[0], vector[1]
    magnitude = math.sqrt(x*x + y*y)
    if magnitude == 0:
        return (0.0, 0.0)

    return (x / magnitude, y / magnitude)

def direction_to(from_pos: tuple[float, float], to_pos: tuple[float, float]):
    dx = to_pos[0] - from_pos[0]
    dy = to_pos[1] - from_pos[1]
    return normalized((dx, dy))

def lerp(start: tuple[float, float], end: tuple[float, float], t: float):
    return (start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)
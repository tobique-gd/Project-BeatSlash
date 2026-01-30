import math

def normalized(vector: tuple[float, float]):
    x,y = vector[0], vector[1]
    magnitude = math.sqrt(x*x + y*y)
    if magnitude == 0:
        return (0.0, 0.0)

    return (x / magnitude, y / magnitude)

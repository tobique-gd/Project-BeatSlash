from ..common import mathlib

PLAYER_DETECT_AREA = None
ACTIVE_PLAYER = None


ACCELERATION = 2.5
target_velocity = (0, 0)

def _ready(self):
    global PLAYER_DETECT_AREA
    PLAYER_DETECT_AREA = self.node.get_node("PlayerDetectArea")

    if PLAYER_DETECT_AREA is None:
        print("Error: PlayerDetectArea node not found in Robu.")
        return

    PLAYER_DETECT_AREA.connect("body_entered", self._on_player_detected)
    PLAYER_DETECT_AREA.connect("body_exited", self._on_player_lost)

def _process(self, delta):
    global ACTIVE_PLAYER
    global ACCELERATION
    global target_velocity
    if ACTIVE_PLAYER is not None:
        DIR = mathlib.normalized(mathlib.direction_to(self.node.global_position, ACTIVE_PLAYER.global_position))
        self.target_velocity = (DIR[0] * 50 * delta, DIR[1] * 50 * delta)
    else:
        self.target_velocity = (0, 0)

    self.node.velocity = mathlib.lerp(self.node.velocity, self.target_velocity, ACCELERATION * delta)
    self.node.move_and_slide()

def _input(self, event):
    pass

def _on_player_detected(self, body):
    global ACTIVE_PLAYER
    if body.name == "Player":
        ACTIVE_PLAYER = body
    
def _on_player_lost(self, body):
    global ACTIVE_PLAYER
    if body.name == "Player":
        ACTIVE_PLAYER = None
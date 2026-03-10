from dataclasses import dataclass
from enum import Enum, auto


class EditorMode(Enum):
    EDIT = auto()
    PLAYTEST = auto()
    PAUSED = auto()


@dataclass
class EditorCommand:
    type: str
    payload: dict

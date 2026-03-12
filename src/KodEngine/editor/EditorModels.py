from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class EditorMode(Enum):
    EDIT = auto()
    PLAYTEST = auto()
    PAUSED = auto()


class EditorCommandType(str, Enum):
    SAVE_SCENE = "save_scene"
    LOAD_SCENE = "load_scene"
    RUN_SCENE = "run_scene"
    RUN_PROJECT = "run_project"
    OPEN_FILE = "open_file"
    OPEN_EDITOR_SETTINGS = "open_editor_settings"


@dataclass
class EditorCommand:
    type: EditorCommandType
    payload: dict[str, Any] = field(default_factory=dict)

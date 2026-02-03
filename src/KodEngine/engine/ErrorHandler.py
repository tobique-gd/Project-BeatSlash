import sys
from datetime import datetime
from typing import Optional, Callable

class ErrorHandler:
    _console_callback: Optional[Callable[[str, str], None]] = None
    _editor_mode: bool = False
    _pending_messages: list[tuple[str, str]] = []
    
    COLORS = {
        "ERROR": (255, 50, 50),
        "WARNING": (255, 200, 50),
        "INFO": (200, 200, 200),
        "SUCCESS": (50, 255, 100)
    }
    
    @classmethod
    def set_console_callback(cls, callback: Callable[[str, str], None]):
        cls._console_callback = callback
        cls._editor_mode = True

        if cls._pending_messages:
            for msg_type, formatted in cls._pending_messages:
                try:
                    cls._console_callback(msg_type, formatted)
                except Exception as e:
                    print(f"ERROR: Failed to write to editor console: {e}", file=sys.stderr)
            cls._pending_messages.clear()

    @classmethod
    def set_editor_mode(cls, enabled: bool = True):
        cls._editor_mode = enabled
    
    @classmethod
    def clear_console_callback(cls):
        cls._console_callback = None
        cls._editor_mode = False
    
    @classmethod
    def _format_message(cls, msg_type: str, message: str, include_timestamp: bool = True) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S") if include_timestamp else ""
        if timestamp:
            return f"[{timestamp}] [{msg_type}]: {message}"
        return f"[{msg_type}]: {message}"
    
    @classmethod
    def _log(cls, msg_type: str, message: str, to_stderr: bool = False):
        formatted = cls._format_message(msg_type, message)
        
        if cls._console_callback is not None:
            try:
                cls._console_callback(msg_type, formatted)
            except Exception as e:
                print(f"ERROR: Failed to write to editor console: {e}", file=sys.stderr)
        elif cls._editor_mode:
            cls._pending_messages.append((msg_type, formatted))
        
        if to_stderr or not cls._editor_mode:
            print(formatted, file=sys.stderr)
    
    @classmethod
    def throw_error(cls, message: str):
        cls._log("ERROR", message)
    
    @classmethod
    def throw_warning(cls, message: str):
        cls._log("WARNING", message)
    
    @classmethod
    def throw_info(cls, message: str):
        cls._log("INFO", message)
    
    @classmethod
    def throw_success(cls, message: str):
        cls._log("SUCCESS", message)
    
    @classmethod
    def is_editor_mode(cls) -> bool:
        return cls._editor_mode

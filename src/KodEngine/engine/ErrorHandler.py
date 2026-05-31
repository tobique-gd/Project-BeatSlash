import sys
from datetime import datetime
from typing import Optional, Callable

class ErrorHandler:
    """Centralized error and status message dispatcher for the engine.

    The handler can either forward messages directly to an editor console
    callback or queue them while editor mode is enabled but no callback is
    attached yet.
    """

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
        """Register the editor console callback used for log output.

        Parameters
        ----------
        callback:
            Callable that receives the message type and formatted message.
            Any messages queued while editor mode was active are flushed to
            this callback immediately.
        """
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
        """Enable or disable editor mode.

        Parameters
        ----------
        enabled:
            When ``True``, messages are queued until a console callback is
            registered. When ``False``, messages are not buffered.
        """
        cls._editor_mode = enabled
    
    @classmethod
    def clear_console_callback(cls):
        """Detach the editor console callback and disable editor mode."""
        cls._console_callback = None
        cls._editor_mode = False
    
    @classmethod
    def _format_message(cls, msg_type: str, message: str, include_timestamp: bool = True) -> str:
        """Format a message for console display.

        Parameters
        ----------
        msg_type:
            Message category such as ``ERROR`` or ``INFO``.
        message:
            Message text to format.
        include_timestamp:
            When ``True``, prefix the message with the current time.

        Returns
        -------
        str
            Formatted console message.
        """
        timestamp = datetime.now().strftime("%H:%M:%S") if include_timestamp else ""
        if timestamp:
            return f"[{timestamp}] [{msg_type}]: {message}"
        return f"[{msg_type}]: {message}"
    
    @classmethod
    def _log(cls, msg_type: str, message: str, to_stderr: bool = False):
        """Dispatch a formatted message to the editor console or queue.

        Parameters
        ----------
        msg_type:
            Message category such as ``ERROR`` or ``WARNING``.
        message:
            Message text to log.
        to_stderr:
            Reserved for future stderr routing. The current implementation
            always forwards through the editor console path when available.
        """
        formatted = cls._format_message(msg_type, message)
        
        if cls._console_callback is not None:
            try:
                cls._console_callback(msg_type, formatted)
            except Exception as e:
                print(f"ERROR: Failed to write to editor console: {e}", file=sys.stderr)
        elif cls._editor_mode:
            cls._pending_messages.append((msg_type, formatted))

    
    @classmethod
    def throw_error(cls, message: str):
        """Log an error message."""
        cls._log("ERROR", message)
    
    @classmethod
    def throw_warning(cls, message: str):
        """Log a warning message."""
        cls._log("WARNING", message)
    
    @classmethod
    def throw_info(cls, message: str):
        """Log an informational message."""
        cls._log("INFO", message)
    
    @classmethod
    def throw_success(cls, message: str):
        """Log a success message."""
        cls._log("SUCCESS", message)
    
    @classmethod
    def is_editor_mode(cls) -> bool:
        """Return whether the handler is currently buffering editor output.

        Returns
        -------
        bool
            ``True`` when editor mode is enabled, otherwise ``False``.
        """
        return cls._editor_mode

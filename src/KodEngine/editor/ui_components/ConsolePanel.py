import dearpygui.dearpygui as pygui
from ...engine.ErrorHandler import ErrorHandler

class ConsolePanel:
    def __init__(self, ui):
        self.ui = ui
        self.messages = []
        self.max_messages = 100
        self.container_tag = "console_container"
        self.filter_state = {
            "ERROR": True,
            "WARNING": True,
            "INFO": True,
            "SUCCESS": True
        }
    
    def build(self):
        with pygui.group(tag=self.container_tag, horizontal=False):
            with pygui.group(horizontal=True):
                pygui.add_text("Console", color=(150, 150, 150))
                pygui.add_button(label="Clear", callback=self.clear_console, width=60)
                
                pygui.add_checkbox(
                    label="Errors", 
                    default_value=True, 
                    callback=lambda s, a: self._toggle_filter("ERROR", a),
                    tag="filter_error"
                )
                pygui.add_checkbox(
                    label="Warnings", 
                    default_value=True, 
                    callback=lambda s, a: self._toggle_filter("WARNING", a),
                    tag="filter_warning"
                )
                pygui.add_checkbox(
                    label="Info", 
                    default_value=True, 
                    callback=lambda s, a: self._toggle_filter("INFO", a),
                    tag="filter_info"
                )
                pygui.add_checkbox(
                    label="Success",
                    default_value=True,
                    callback=lambda s, a: self._toggle_filter("SUCCESS", a),
                    tag="filter_success"
                )
            
            pygui.add_separator()
            
            with pygui.child_window(tag="console_messages", height=-1, border=False):
                pygui.add_text("[Log]: Console initialized.", color=ErrorHandler.COLORS["INFO"])

        self._refresh_display()
    
    def _toggle_filter(self, msg_type: str, enabled: bool):
        self.filter_state[msg_type] = enabled
        self._refresh_display()
    
    def add_message(self, msg_type: str, message: str):
        color = ErrorHandler.COLORS.get(msg_type, (255, 255, 255))
        
        self.messages.append({"type": msg_type, "text": message, "color": color})
        
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
    
        if self.filter_state.get(msg_type, True):
            self._add_message_to_ui(message, color)
    
    def _add_message_to_ui(self, message: str, color: tuple):
        if pygui.does_item_exist("console_messages"):
            pygui.add_text(message, color=color, parent="console_messages")
            
            if pygui.does_item_exist("console_messages"):
                pygui.set_y_scroll("console_messages", pygui.get_y_scroll_max("console_messages"))
    
    def clear_console(self):
        self.messages.clear()
        if pygui.does_item_exist("console_messages"):
            pygui.delete_item("console_messages", children_only=True)
            pygui.add_text("[Log]: Console cleared.", color=ErrorHandler.COLORS["INFO"], parent="console_messages")
    
    def _refresh_display(self):
        if not pygui.does_item_exist("console_messages"):
            return
        
        pygui.delete_item("console_messages", children_only=True)
        
        for msg in self.messages:
            if self.filter_state.get(msg["type"], True):
                pygui.add_text(msg["text"], color=msg["color"], parent="console_messages")
        
        if pygui.does_item_exist("console_messages"):
            pygui.set_y_scroll("console_messages", pygui.get_y_scroll_max("console_messages"))

import dearpygui.dearpygui as pygui

class ViewportPanel:
    def __init__(self, ui):
        self.ui = ui

    def create_texture(self):
        if pygui.does_alias_exist("engine_texture"):
            pygui.remove_alias("engine_texture")

        if pygui.does_item_exist("engine_texture"):
            pygui.delete_item("engine_texture")

        with pygui.texture_registry(show=False):
            initial_data = [0.0] * (self.ui.editor.width * self.ui.editor.height * 4)
            pygui.add_raw_texture(
                width=self.ui.editor.width,
                height=self.ui.editor.height,
                default_value=initial_data,
                tag="engine_texture"
            )

    def check_resize(self):
        if not pygui.does_item_exist("viewport_container"):
            return

        size = pygui.get_item_rect_size("viewport_container")
        new_w = max(int(size[0] - 10), 100)
        new_h = max(int(size[1] - 40), 100)

        if self.ui.editor.update_viewport_size(new_w, new_h):
            self.create_texture()
            
            if pygui.does_item_exist("viewport_image"):
                pygui.configure_item("viewport_image", texture_tag="engine_texture")
                pygui.configure_item("viewport_image", width=new_w, height=new_h)

    def push_frame(self, frame):
        if pygui.does_item_exist("engine_texture"):
            try:
                pygui.set_value("engine_texture", frame.flatten())
            except Exception:
                pass
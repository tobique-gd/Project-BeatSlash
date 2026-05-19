import dearpygui.dearpygui as pygui

class ViewportPanel:
    def __init__(self, ui):
        self.ui = ui

    def create_texture(self):
        if pygui.does_alias_exist("engine_texture"):
            pygui.remove_alias("engine_texture")

        if pygui.does_item_exist("engine_texture"):
            pygui.delete_item("engine_texture")

        texture_width = max(1, int(self.ui.editor.display_width))
        texture_height = max(1, int(self.ui.editor.display_height))

        with pygui.texture_registry(show=False):
            initial_data = [0.0] * (texture_width * texture_height * 4)
            pygui.add_raw_texture(
                width=texture_width,
                height=texture_height,
                default_value=initial_data,
                tag="engine_texture"
            )

    def check_resize(self):
        if not pygui.does_item_exist("viewport_container"):
            return

        size = pygui.get_item_rect_size("viewport_container")
        available_w = max(int(size[0] - 10), 100)
        available_h = max(int(size[1] - 40), 100)

        resized, texture_changed = self.ui.editor.update_viewport_size(available_w, available_h)
        if resized:
            if texture_changed:
                self.create_texture()
            if pygui.does_item_exist("viewport_image"):
                pygui.configure_item("viewport_image", texture_tag="engine_texture")
                pygui.configure_item("viewport_image", width=available_w, height=available_h)

    def push_frame(self, frame):
        if pygui.does_item_exist("engine_texture"):
            try:
                pygui.set_value("engine_texture", frame.flatten())
            except Exception:
                pass
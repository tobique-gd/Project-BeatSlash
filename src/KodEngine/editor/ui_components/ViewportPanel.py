import os
import dearpygui.dearpygui as pygui

class ViewportPanel:
    def __init__(self, ui):
        self.ui = ui
        self._tab_tag_by_path: dict[str, str] = {}

    def _normalize_scene_path(self, scene_path):
        if not scene_path:
            return None
        try:
            return os.path.abspath(scene_path)
        except Exception:
            return scene_path

    def _scene_display_name(self, scene_path):
        if not scene_path:
            return "Untitled"
        base = os.path.basename(scene_path)
        name, _ = os.path.splitext(base)
        return name or base

    def _ensure_current_scene_tab(self):
        current_scene = getattr(self.ui.app, "current_scene", None)
        scene_path = getattr(current_scene, "path", None) if current_scene else None
        if scene_path:
            self.register_scene(scene_path, make_active=True, refresh_ui=False)

    def register_scene(self, scene_path, make_active=True, refresh_ui=True):
        normalized = self._normalize_scene_path(scene_path)
        if not normalized:
            return

        tabs = self.ui.state.open_scene_tabs
        if normalized not in tabs:
            tabs.append(normalized)

        if make_active:
            self.ui.state.active_scene_path = normalized

        if refresh_ui:
            self.build_tabs()
            
        try:
            if not getattr(self.ui.editor, "_restoring_state", False):
                self.ui.editor._save_editor_state()
        except Exception:
            pass

    def close_scene_tab(self, scene_path, refresh_ui=True):
        normalized = self._normalize_scene_path(scene_path)
        if not normalized:
            return

        tabs = self.ui.state.open_scene_tabs
        if normalized not in tabs:
            return

        active = self.ui.state.active_scene_path
        idx = tabs.index(normalized)
        tabs.remove(normalized)

        if active == normalized:
            new_active = None
            if tabs:
                if idx >= len(tabs):
                    new_active = tabs[-1]
                else:
                    new_active = tabs[idx]

            self.ui.state.active_scene_path = new_active
            if new_active and getattr(self.ui.app.current_scene, "path", None) != new_active:
                self.ui.editor.load_scene(new_active)

        if refresh_ui:
            self.build_tabs()
            
        try:
            if not getattr(self.ui.editor, "_restoring_state", False):
                self.ui.editor._save_editor_state()
        except Exception:
            pass

    def set_active_scene(self, scene_path):
        normalized = self._normalize_scene_path(scene_path)
        if not normalized:
            return

        self.register_scene(normalized, make_active=True, refresh_ui=False)
        if getattr(self.ui.app.current_scene, "path", None) != normalized:
            self.ui.editor.load_scene(normalized)


    def _ensure_tab_theme(self):
        if pygui.does_item_exist("viewport_tab_theme"):
            return

        with pygui.theme(tag="viewport_tab_theme"):
            with pygui.theme_component(pygui.mvTab):
                pygui.add_theme_color(pygui.mvThemeCol_Tab, (40, 44, 52, 255))
                pygui.add_theme_color(pygui.mvThemeCol_TabHovered, (62, 88, 140, 255))
                pygui.add_theme_color(pygui.mvThemeCol_TabActive, (74, 110, 180, 255))

    def _on_tab_bar_selected(self, sender, app_data):
        selected = app_data
        if isinstance(selected, (list, tuple)):
            selected = selected[0] if selected else None

        if not selected:
            try:
                selected = pygui.get_value(sender)
            except Exception:
                selected = None

        if not selected:
            return

        scene_path = None
        try:
            scene_path = pygui.get_item_user_data(selected)
        except Exception:
            scene_path = None

        if not scene_path:
            scene_path = self._tab_tag_by_path.get(str(selected))

        if scene_path:
            self.set_active_scene(scene_path)

    def _sync_tab_closures(self):
        if not pygui.does_item_exist("viewport_tab_bar"):
            return

        closed_paths = []
        for tag, path in list(self._tab_tag_by_path.items()):
            if not pygui.does_item_exist(tag):
                closed_paths.append(path)

        if not closed_paths:
            return

        for path in closed_paths:
            self.close_scene_tab(path, refresh_ui=False)

        self.build_tabs()

    def build_tabs(self):
        if not pygui.does_item_exist("viewport_tabs"):
            return
        self._ensure_tab_theme()

        pygui.delete_item("viewport_tabs", children_only=True)

        tabs = list(self.ui.state.open_scene_tabs)
        active = self.ui.state.active_scene_path

        self._tab_tag_by_path.clear()
        active_tag = None

        with pygui.tab_bar(parent="viewport_tabs", tag="viewport_tab_bar", callback=self._on_tab_bar_selected):
            for idx, scene_path in enumerate(tabs):
                label = self._scene_display_name(scene_path)
                tag = f"viewport_tab::{idx}"
                self._tab_tag_by_path[tag] = scene_path
                pygui.add_tab(label=label, tag=tag, closable=True, user_data=scene_path)
                if scene_path == active:
                    active_tag = tag

        pygui.bind_item_theme("viewport_tab_bar", "viewport_tab_theme")

        if active_tag is not None:
            try:
                pygui.set_value("viewport_tab_bar", active_tag)
            except Exception:
                pass

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
        self._sync_tab_closures()
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
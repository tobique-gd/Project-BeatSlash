import dearpygui.dearpygui as pygui
import numpy as np
import pygame
import os

from ..engine import Resources
from ..engine import ErrorHandler


class ResourceEditorRegistry:
    def __init__(self):
        self._editors: dict[type, type[BaseResourceEditor]] = {}

    def register(self, resource_cls: type, editor_cls: type["BaseResourceEditor"]) -> None:
        self._editors[resource_cls] = editor_cls

    def get_editor(self, resource: Resources.Resource) -> "BaseResourceEditor":
        for cls in type(resource).mro():
            editor_cls = self._editors.get(cls)
            if editor_cls is not None:
                return editor_cls()
        return BaseResourceEditor()


class BaseResourceEditor:
    excluded_fields = {"type_id", "resource_path", "extensions"}

    def _is_path_attr(self, attr: str):
        return attr == "resource_path" or attr.endswith("_path")

    def _to_display_path(self, value, editor_context: dict | None):
        if not isinstance(value, str) or not value:
            return "<Local>"

        if isinstance(editor_context, dict):
            to_relative = editor_context.get("to_relative_path")
            if callable(to_relative):
                try:
                    return str(to_relative(value))
                except Exception:
                    return value

        return value

    def _open_path_picker(self, resource: Resources.Resource, attr: str, on_changed, editor_context: dict | None):
        if not isinstance(attr, str) or not attr:
            return

        if not isinstance(editor_context, dict):
            return

        open_picker = editor_context.get("open_file_picker")
        if not callable(open_picker):
            return

        extensions = getattr(type(resource), "extensions", ())
        current_path = getattr(resource, attr, None)

        if attr == "spritesheet_path":
            extensions = Resources.Texture2D.extensions

        open_picker(
            title=f"Select {attr.replace('_', ' ').title()}",
            on_selected=lambda selected_path: self._set_resource_path(resource, attr, selected_path, on_changed),
            extensions=tuple(extensions) if isinstance(extensions, (list, tuple)) else None,
            initial_path=current_path,
        )

    def _set_resource_path(self, resource: Resources.Resource, attr: str, path: str, on_changed):
        setattr(resource, attr, path)

        if attr == "resource_path":
            if hasattr(resource, "texture_path"):
                setattr(resource, "texture_path", path)
            if hasattr(resource, "file_path"):
                setattr(resource, "file_path", path)
            if hasattr(resource, "script_path"):
                setattr(resource, "script_path", path)
        elif self._is_path_attr(attr) and hasattr(resource, "resource_path"):
            setattr(resource, "resource_path", path)

        load_texture = getattr(resource, "load_texture", None)
        if callable(load_texture) and attr in ("resource_path", "texture_path", "spritesheet_path"):
            try:
                load_texture(path)
            except Exception:
                pass

        load_audio = getattr(resource, "load_audio", None)
        if callable(load_audio) and attr in ("resource_path", "file_path"):
            try:
                load_audio(path)
            except Exception:
                pass

        reload_fn = getattr(resource, "reload", None)
        if callable(reload_fn):
            try:
                reload_fn()
            except Exception:
                pass

        on_changed()

    def _from_display_path(self, path_value: str, editor_context: dict | None):
        normalized = path_value.strip()
        if not normalized:
            return ""

        if isinstance(editor_context, dict):
            from_relative = editor_context.get("from_relative_path")
            if callable(from_relative):
                try:
                    return str(from_relative(normalized))
                except Exception:
                    return normalized
        return normalized

    def _set_path_from_input(self, resource: Resources.Resource, attr: str, value: str, on_changed, editor_context: dict | None):
        normalized = self._from_display_path(value, editor_context)
        if not normalized:
            setattr(resource, attr, None)
            if self._is_path_attr(attr) and hasattr(resource, "resource_path"):
                setattr(resource, "resource_path", None)
            on_changed()
            return

        self._set_resource_path(resource, attr, normalized, on_changed)

    def _apply_path_from_input_tag(self, resource: Resources.Resource, attr: str, input_tag: str, on_changed, editor_context: dict | None):
        if not pygui.does_item_exist(input_tag):
            return

        try:
            raw_value = pygui.get_value(input_tag)
        except Exception:
            raw_value = ""

        self._set_path_from_input(resource, attr, str(raw_value or ""), on_changed, editor_context)

    def _iter_editable_fields(self, resource: Resources.Resource):
        for attr, value in vars(resource).items():
            if attr.startswith("_"):
                continue
            if attr in self.excluded_fields:
                continue
            if callable(value):
                continue
            yield attr, value

    def draw(self, parent: str, resource: Resources.Resource, on_changed, editor_context: dict | None = None):
        with pygui.table(parent=parent, header_row=False, resizable=True):
            pygui.add_table_column(init_width_or_weight=0.35)
            pygui.add_table_column(init_width_or_weight=0.65)

            with pygui.table_row():
                pygui.add_text("Type")
                pygui.add_text(getattr(resource, "type_id", type(resource).__name__))

            with pygui.table_row():
                pygui.add_text("Path")
                path_input_tag = f"##tileset_path_{id(resource)}"
                with pygui.group(horizontal=True):
                    pygui.add_input_text(
                        tag=path_input_tag,
                        label=path_input_tag,
                        default_value=self._to_display_path(getattr(resource, "resource_path", None), editor_context) if getattr(resource, "resource_path", None) else "",
                        width=-180,
                    )
                    pygui.add_button(
                        label="Set",
                        width=50,
                        callback=lambda: self._apply_path_from_input_tag(resource, "resource_path", path_input_tag, on_changed, editor_context),
                    )
                    pygui.add_button(
                        label="Browse",
                        width=70,
                        callback=lambda *_, r=resource: self._open_path_picker(r, "resource_path", on_changed, editor_context),
                    )

            for attr, value in self._iter_editable_fields(resource):
                self._draw_value_row(resource, attr, value, on_changed, editor_context)

    def _draw_value_row(self, resource: Resources.Resource, attr: str, value, on_changed, editor_context: dict | None = None):
        label = attr.replace("_", " ").title()

        if isinstance(value, bool):
            with pygui.table_row():
                pygui.add_text(label)
                pygui.add_checkbox(
                    label=f"##resource_{id(resource)}_{attr}",
                    default_value=value,
                    callback=lambda s, v, r=resource, a=attr: self._set_value(r, a, bool(v), on_changed),
                )
            return

        if isinstance(value, int):
            with pygui.table_row():
                pygui.add_text(label)
                pygui.add_drag_int(
                    label=f"##resource_{id(resource)}_{attr}",
                    default_value=value,
                    width=-1,
                    callback=lambda s, v, r=resource, a=attr: self._set_value(r, a, int(v), on_changed),
                )
            return

        if isinstance(value, float):
            with pygui.table_row():
                pygui.add_text(label)
                pygui.add_drag_float(
                    label=f"##resource_{id(resource)}_{attr}",
                    default_value=value,
                    width=-1,
                    callback=lambda s, v, r=resource, a=attr: self._set_value(r, a, float(v), on_changed),
                )
            return

        if isinstance(value, str):
            if self._is_path_attr(attr):
                with pygui.table_row():
                    pygui.add_text(label)
                    with pygui.group(horizontal=True):
                        pygui.add_input_text(
                            label=f"##resource_{id(resource)}_{attr}",
                            default_value=self._to_display_path(value, editor_context),
                            width=-90,
                            on_enter=True,
                            callback=lambda s, v, r=resource, a=attr: self._set_path_from_input(r, a, str(v), on_changed, editor_context),
                        )
                        pygui.add_button(
                            label="Browse",
                            width=80,
                            callback=lambda *_, r=resource, field=attr: self._open_path_picker(r, field, on_changed, editor_context),
                        )
                return

            with pygui.table_row():
                pygui.add_text(label)
                pygui.add_input_text(
                    label=f"##resource_{id(resource)}_{attr}",
                    default_value=value,
                    width=-1,
                    on_enter=True,
                    callback=lambda s, v, r=resource, a=attr: self._set_value(r, a, str(v), on_changed),
                )
            return

        if isinstance(value, (tuple, list)) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
            vec = [float(value[0]), float(value[1])]
            with pygui.table_row():
                pygui.add_text(label)
                pygui.add_drag_floatx(
                    label=f"##resource_{id(resource)}_{attr}",
                    default_value=vec,
                    size=2,
                    width=-1,
                    callback=lambda s, v, r=resource, a=attr, old=value: self._set_vec2(r, a, v, old, on_changed),
                )
            return

        with pygui.table_row():
            pygui.add_text(label)
            pygui.add_text(str(value))

    def _set_value(self, resource: Resources.Resource, attr: str, value, on_changed):
        setattr(resource, attr, value)
        on_changed()

    def _set_vec2(self, resource: Resources.Resource, attr: str, value, old_value, on_changed):
        if isinstance(old_value, tuple):
            if all(isinstance(v, int) for v in old_value[:2]):
                new_value = (int(value[0]), int(value[1]))
            else:
                new_value = (float(value[0]), float(value[1]))
        else:
            if all(isinstance(v, int) for v in old_value[:2]):
                new_value = [int(value[0]), int(value[1])]
            else:
                new_value = [float(value[0]), float(value[1])]

        setattr(resource, attr, new_value)
        on_changed()


class SpriteAnimationEditor(BaseResourceEditor):
    _texture_registry_tag = "resource_editor_anim_texture_registry"

    def draw(self, parent: str, resource: Resources.Resource, on_changed, editor_context: dict | None = None):
        if not isinstance(resource, Resources.SpriteAnimation):
            super().draw(parent, resource, on_changed, editor_context=editor_context)
            return

        anim = resource

        with pygui.table(parent=parent, header_row=False, resizable=True):
            pygui.add_table_column(init_width_or_weight=0.35)
            pygui.add_table_column(init_width_or_weight=0.65)

            with pygui.table_row():
                pygui.add_text("Type")
                pygui.add_text(getattr(anim, "type_id", type(anim).__name__))

            with pygui.table_row():
                pygui.add_text("Path")
                path_value = getattr(anim, "resource_path", None)
                path_label = self._to_display_path(path_value, editor_context)
                pygui.add_button(
                    label=path_label,
                    width=-1,
                    callback=lambda *_, r=anim: self._open_path_picker(r, "resource_path", on_changed, editor_context),
                )

            with pygui.table_row():
                pygui.add_text("Name")
                pygui.add_input_text(
                    label=f"##sprite_anim_name_{id(anim)}",
                    default_value=str(anim.name),
                    width=-1,
                    on_enter=True,
                    callback=lambda s, v: self._set_value(anim, "name", str(v), on_changed),
                )

            with pygui.table_row():
                pygui.add_text("Spritesheet Path")
                with pygui.group(horizontal=True):
                    pygui.add_input_text(
                        label=f"##sprite_anim_sheet_{id(anim)}",
                        default_value=self._to_display_path(str(anim.spritesheet_path or ""), editor_context),
                        width=-90,
                        on_enter=True,
                        callback=lambda s, v: self._set_spritesheet(anim, str(v), on_changed, editor_context),
                    )
                    pygui.add_button(
                        label="Browse",
                        width=80,
                        callback=lambda *_, r=anim: self._open_spritesheet_picker(r, on_changed, editor_context),
                    )

            with pygui.table_row():
                pygui.add_text("Frame Size")
                pygui.add_drag_intx(
                    label=f"##sprite_anim_frame_size_{id(anim)}",
                    default_value=[int(anim.frame_size[0]), int(anim.frame_size[1])],
                    size=2,
                    min_value=1,
                    max_value=8192,
                    width=-1,
                    callback=lambda s, v: self._set_frame_size(anim, v, on_changed),
                )

            with pygui.table_row():
                pygui.add_text("Frames")
                selected_count = len(getattr(anim, "frame_regions", []) or [])
                label = str(int(anim.frames))
                if selected_count > 0:
                    label = f"{selected_count} selected"
                pygui.add_text(label)

            with pygui.table_row():
                pygui.add_text("FPS")
                pygui.add_drag_int(
                    label=f"##sprite_anim_fps_{id(anim)}",
                    default_value=int(anim.fps),
                    min_value=1,
                    max_value=240,
                    width=-1,
                    callback=lambda s, v: self._set_value(anim, "fps", int(v), on_changed),
                )

            with pygui.table_row():
                pygui.add_text("Loop")
                pygui.add_checkbox(
                    label=f"##sprite_anim_loop_{id(anim)}",
                    default_value=bool(anim.loop),
                    callback=lambda s, v: self._set_value(anim, "loop", bool(v), on_changed),
                )

        pygui.add_separator(parent=parent)

        with pygui.group(parent=parent, horizontal=True):
            pygui.add_button(
                label="Select All Grid Frames",
                width=180,
                callback=lambda: self._select_all_frames(anim, on_changed),
            )
            pygui.add_button(
                label="Clear Selection",
                width=150,
                callback=lambda: self._clear_frame_selection(anim, on_changed),
            )
            pygui.add_button(
                label="Reload Frames",
                width=-1,
                callback=lambda: self._reload_animation(anim, on_changed),
            )

        pygui.add_separator(parent=parent)
        self._draw_spritesheet_selection_preview(parent, anim, on_changed)

        pygui.add_separator(parent=parent)
        self._draw_selected_frames_list(parent, anim, on_changed)

    def _set_spritesheet(self, resource: Resources.SpriteAnimation, path: str, on_changed, editor_context: dict | None):
        normalized = self._from_display_path(path, editor_context)
        if not normalized:
            resource.spritesheet_path = None
            resource.spritesheet = None
            resource.frame_regions = []
            resource.frames = 0
            resource.reload()
            on_changed()
            return

        resource.spritesheet_path = normalized
        resource.spritesheet = Resources.Texture2D(resource_path=normalized)
        resource.reload()
        on_changed()

    def _open_spritesheet_picker(self, resource: Resources.SpriteAnimation, on_changed, editor_context: dict | None):
        if not isinstance(editor_context, dict):
            return

        open_picker = editor_context.get("open_file_picker")
        if not callable(open_picker):
            return

        open_picker(
            title="Select Spritesheet",
            on_selected=lambda selected_path: self._set_spritesheet(resource, selected_path, on_changed, editor_context),
            extensions=Resources.Texture2D.extensions,
            initial_path=resource.spritesheet_path,
        )

    def _set_frame_size(self, resource: Resources.SpriteAnimation, value, on_changed):
        resource.frame_size = (max(1, int(value[0])), max(1, int(value[1])))
        resource.reload()
        on_changed()

    def _draw_spritesheet_selection_preview(self, parent: str, resource: Resources.SpriteAnimation, on_changed):
        if not isinstance(resource.spritesheet, Resources.Texture2D):
            pygui.add_text("Assign a spritesheet to select animation frames.", parent=parent)
            return

        sheet_surface = resource.spritesheet.get_texture()
        if sheet_surface is None:
            pygui.add_text("Failed to load the selected spritesheet.", parent=parent)
            return

        frame_w = max(1, int(resource.frame_size[0]))
        frame_h = max(1, int(resource.frame_size[1]))
        cols = max(1, sheet_surface.get_width() // frame_w)
        rows = max(1, sheet_surface.get_height() // frame_h)

        selected_regions = getattr(resource, "frame_regions", []) or []
        pygui.add_text(
            f"Spritesheet Grid: {cols} x {rows} | Frame: {frame_w} x {frame_h} | Selected: {len(selected_regions)}",
            parent=parent,
            color=(150, 150, 150),
        )
        pygui.add_text(
            "Click the preview to toggle one frame in sequence order.",
            parent=parent,
            color=(130, 130, 130),
        )

        preview_tag = f"sprite_anim_sheet_preview_{id(resource)}"
        self._update_texture(preview_tag, sheet_surface)

        max_preview_size = 420.0
        scale = min(1.0, max_preview_size / max(1, max(sheet_surface.get_width(), sheet_surface.get_height())))
        display_width = max(1, int(sheet_surface.get_width() * scale))
        display_height = max(1, int(sheet_surface.get_height() * scale))

        pygui.add_image_button(
            texture_tag=preview_tag,
            parent=parent,
            width=display_width,
            height=display_height,
            frame_padding=0,
            callback=lambda sender, app_data: self._toggle_frame_from_preview(sender, resource, on_changed, scale),
        )

    def _toggle_frame_from_preview(self, sender, resource: Resources.SpriteAnimation, on_changed, scale: float):
        if not isinstance(resource.spritesheet, Resources.Texture2D):
            return

        sheet_surface = resource.spritesheet.get_texture()
        if sheet_surface is None:
            return

        frame_w = max(1, int(resource.frame_size[0]))
        frame_h = max(1, int(resource.frame_size[1]))

        mouse_x, mouse_y = pygui.get_mouse_pos(local=False)
        rect_min = pygui.get_item_rect_min(sender)
        local_x = max(0, int((mouse_x - rect_min[0]) / max(scale, 0.001)))
        local_y = max(0, int((mouse_y - rect_min[1]) / max(scale, 0.001)))

        origin_x = (local_x // frame_w) * frame_w
        origin_y = (local_y // frame_h) * frame_h
        if origin_x + frame_w > sheet_surface.get_width() or origin_y + frame_h > sheet_surface.get_height():
            return

        target_region = ((int(origin_x), int(origin_y)), (int(frame_w), int(frame_h)))
        frame_regions = list(getattr(resource, "frame_regions", []) or [])
        if target_region in frame_regions:
            frame_regions = [region for region in frame_regions if region != target_region]
        else:
            frame_regions.append(target_region)

        resource.frame_regions = frame_regions
        resource.frames = len(frame_regions)
        resource.reload()
        on_changed()

    def _draw_selected_frames_list(self, parent: str, resource: Resources.SpriteAnimation, on_changed):
        frame_regions = list(getattr(resource, "frame_regions", []) or [])
        pygui.add_text("Selected Frames", parent=parent, color=(150, 150, 150))
        if not frame_regions:
            pygui.add_text("No frames selected. Click spritesheet preview to add frames.", parent=parent)
            return

        with pygui.child_window(parent=parent, border=True, height=180):
            for index, region in enumerate(frame_regions):
                (x, y), (w, h) = region
                with pygui.group(horizontal=True):
                    pygui.add_text(f"{index}: ({x}, {y}) {w}x{h}")
                    pygui.add_button(
                        label=f"Remove##anim_frame_remove_{id(resource)}_{index}",
                        width=80,
                        callback=lambda *_, idx=index: self._remove_selected_frame(resource, idx, on_changed),
                    )

    def _remove_selected_frame(self, resource: Resources.SpriteAnimation, index: int, on_changed):
        frame_regions = list(getattr(resource, "frame_regions", []) or [])
        if index < 0 or index >= len(frame_regions):
            return
        frame_regions.pop(index)
        resource.frame_regions = frame_regions
        resource.frames = len(frame_regions)
        resource.reload()
        on_changed()

    def _select_all_frames(self, resource: Resources.SpriteAnimation, on_changed):
        if not isinstance(resource.spritesheet, Resources.Texture2D):
            return

        sheet_surface = resource.spritesheet.get_texture()
        if sheet_surface is None:
            return

        frame_w = max(1, int(resource.frame_size[0]))
        frame_h = max(1, int(resource.frame_size[1]))
        cols = sheet_surface.get_width() // frame_w
        rows = sheet_surface.get_height() // frame_h

        frame_regions = []
        for y in range(rows):
            for x in range(cols):
                frame_regions.append(((x * frame_w, y * frame_h), (frame_w, frame_h)))

        resource.frame_regions = frame_regions
        resource.frames = len(frame_regions)
        resource.reload()
        on_changed()

    def _clear_frame_selection(self, resource: Resources.SpriteAnimation, on_changed):
        resource.frame_regions = []
        resource.frames = 0
        resource.reload()
        on_changed()

    def _reload_animation(self, resource: Resources.SpriteAnimation, on_changed):
        resource.reload()
        on_changed()

    def _ensure_texture_registry(self):
        if not pygui.does_item_exist(self._texture_registry_tag):
            with pygui.texture_registry(tag=self._texture_registry_tag, show=False):
                pass
        return self._texture_registry_tag

    def _update_texture(self, texture_tag: str, surface: pygame.Surface):
        if surface is None:
            return

        registry_tag = self._ensure_texture_registry()
        rgba = pygame.surfarray.array3d(surface).transpose((1, 0, 2))
        alpha = pygame.surfarray.array_alpha(surface).transpose((1, 0))[..., np.newaxis]
        texture_data = np.concatenate((rgba, alpha), axis=2).astype(np.float32) / 255.0

        if pygui.does_item_exist(texture_tag):
            pygui.delete_item(texture_tag)

        pygui.add_static_texture(
            width=surface.get_width(),
            height=surface.get_height(),
            default_value=texture_data.flatten().tolist(),
            tag=texture_tag,
            parent=registry_tag,
        )


class Tileset2DEditor(BaseResourceEditor):
    _texture_registry_tag = "resource_editor_texture_registry"

    def draw(self, parent: str, resource: Resources.Resource, on_changed, editor_context: dict | None = None):
        if not isinstance(resource, Resources.Tileset2D):
            super().draw(parent, resource, on_changed, editor_context=editor_context)
            return

        resource.ensure_default_tile()
        selected_tile = self._get_selected_tile(resource)

        with pygui.table(parent=parent, header_row=False, resizable=True):
            pygui.add_table_column(init_width_or_weight=0.35)
            pygui.add_table_column(init_width_or_weight=0.65)

            with pygui.table_row():
                pygui.add_text("Type")
                pygui.add_text(getattr(resource, "type_id", type(resource).__name__))

            with pygui.table_row():
                pygui.add_text("Path")
                path_value = getattr(resource, "resource_path", None)
                path_label = self._to_display_path(path_value, editor_context)
                pygui.add_button(
                    label=path_label,
                    width=-1,
                    callback=lambda *_, r=resource: self._show_tileset_save_dialog(r, on_changed, editor_context),
                )

            with pygui.table_row():
                pygui.add_text("Name")
                pygui.add_input_text(
                    label=f"##tileset_name_{id(resource)}",
                    default_value=str(resource.name),
                    width=-1,
                    on_enter=True,
                    callback=lambda s, v: self._set_value(resource, "name", str(v), on_changed),
                )

            with pygui.table_row():
                pygui.add_text("Tile Size")
                pygui.add_drag_intx(
                    label=f"##tileset_size_{id(resource)}",
                    default_value=[int(resource.tile_size[0]), int(resource.tile_size[1])],
                    size=2,
                    min_value=1,
                    max_value=8192,
                    width=-1,
                    callback=lambda s, v: self._set_tile_size(resource, v, on_changed),
                )

            with pygui.table_row():
                pygui.add_text("Tilesheet")
                with pygui.group(horizontal=True):
                    pygui.add_input_text(
                        label=f"##tileset_sheet_{id(resource)}",
                        default_value=self._to_display_path(self._tilesheet_path(resource), editor_context) if self._tilesheet_path(resource) else "",
                        width=-90,
                        on_enter=True,
                        callback=lambda s, v: self._set_tilesheet(resource, str(v), on_changed, editor_context),
                    )
                    pygui.add_button(
                        label="Browse",
                        width=80,
                        callback=lambda *_, r=resource: self._open_tilesheet_picker(r, on_changed, editor_context),
                    )

        pygui.add_separator(parent=parent)

        with pygui.group(parent=parent, horizontal=True):
            pygui.add_button(
                label="Add Tile",
                width=170,
                callback=lambda: self._add_tile(resource, on_changed),
            )
            pygui.add_button(
                label="Remove Tile",
                width=170,
                callback=lambda: self._remove_selected_tile(resource, on_changed),
            )
            pygui.add_button(
                label="Save Tileset",
                width=-1,
                callback=lambda: self._save_tileset(resource, on_changed),
            )

        pygui.add_separator(parent=parent)

        with pygui.group(parent=parent, horizontal=True):
            with pygui.child_window(width=220, height=260, border=True):
                pygui.add_text("Tiles", color=(150, 150, 150))
                pygui.add_separator()
                for tile in resource.tiles:
                    label = f"{tile.id}: {tile.name}"
                    if selected_tile is not None and tile.id == selected_tile.id:
                        label = f"> {label}"
                    pygui.add_button(
                        label=label,
                        width=-1,
                        callback=lambda *_, tile_id=tile.id: self._select_tile(resource, tile_id, on_changed),
                    )

            with pygui.child_window(width=-1, height=260, border=False):
                self._draw_selected_tile_editor(resource, selected_tile, on_changed)

        pygui.add_separator(parent=parent)
        self._draw_tilesheet_preview(parent, resource, selected_tile, on_changed)

    def _tilesheet_path(self, resource: Resources.Tileset2D):
        if isinstance(resource.tilesheet, Resources.Texture2D):
            return resource.tilesheet.resource_path or resource.tilesheet.texture_path
        return None

    def _get_selected_tile(self, resource: Resources.Tileset2D):
        selected_id = self._get_selected_tile_id(resource)
        selected_tile = resource.get_tile_by_id(selected_id) if selected_id is not None else None
        if selected_tile is not None:
            return selected_tile

        if not resource.tiles:
            return None

        selected_tile = resource.tiles[0]
        self._set_selected_tile_id(resource, selected_tile.id)
        return selected_tile

    def _select_tile(self, resource: Resources.Tileset2D, tile_id: int, on_changed):
        self._set_selected_tile_id(resource, int(tile_id))
        on_changed()

    def _get_selected_tile_id(self, resource: Resources.Tileset2D):
        return getattr(resource, "_editor_selected_tile_id", None)

    def _set_selected_tile_id(self, resource: Resources.Tileset2D, tile_id: int | None):
        setattr(resource, "_editor_selected_tile_id", tile_id)

    def _set_tile_size(self, resource: Resources.Tileset2D, value, on_changed):
        resource.tile_size = (max(1, int(value[0])), max(1, int(value[1])))
        resource.clear_runtime_cache()
        on_changed()

    def _set_tilesheet(self, resource: Resources.Tileset2D, path: str, on_changed, editor_context: dict | None):
        normalized = self._from_display_path(path, editor_context)
        if not normalized:
            resource.tilesheet = None
            resource.clear_runtime_cache()
            on_changed()
            return

        resource.tilesheet = Resources.Texture2D(resource_path=normalized)
        resource.clear_runtime_cache()
        on_changed()

    def _project_root_from_context(self, editor_context: dict | None):
        if isinstance(editor_context, dict):
            from_relative = editor_context.get("from_relative_path")
            if callable(from_relative):
                try:
                    root = from_relative(".")
                    if isinstance(root, str) and root:
                        return os.path.abspath(root)
                except Exception:
                    pass
        return os.getcwd()

    def _relative_display(self, path: str, editor_context: dict | None):
        if not isinstance(path, str) or not path:
            return ""
        if isinstance(editor_context, dict):
            to_relative = editor_context.get("to_relative_path")
            if callable(to_relative):
                try:
                    return str(to_relative(path))
                except Exception:
                    return path
        return path

    def _show_tileset_save_dialog(self, resource: Resources.Tileset2D, on_changed, editor_context: dict | None):
        window_tag = f"tileset_save_dialog_{id(resource)}"
        folder_display_tag = f"tileset_save_folder_display_{id(resource)}"
        filename_tag = f"tileset_save_filename_{id(resource)}"
        tree_tag = f"tileset_save_tree_{id(resource)}"

        root_folder = self._project_root_from_context(editor_context)

        current_path = getattr(resource, "resource_path", None)
        if isinstance(current_path, str) and current_path:
            initial_folder = os.path.dirname(current_path)
            initial_filename = os.path.basename(current_path)
        else:
            initial_folder = root_folder
            initial_filename = "new_tileset.tileset"

        if not initial_filename.lower().endswith(".tileset"):
            initial_filename = f"{initial_filename}.tileset"

        setattr(resource, "_editor_save_folder", initial_folder)

        if pygui.does_item_exist(window_tag):
            pygui.delete_item(window_tag)

        with pygui.window(
            label="Set Tileset Save Path",
            tag=window_tag,
            width=700,
            height=540,
            no_collapse=True,
            modal=False,
        ):
            pygui.add_text("1) Select folder")
            pygui.add_input_text(
                tag=folder_display_tag,
                default_value=self._relative_display(initial_folder, editor_context),
                width=-1,
                readonly=True,
            )

            pygui.add_separator()
            with pygui.child_window(tag=tree_tag, border=True, height=330):
                self._draw_folder_tree(root_folder, resource, editor_context, folder_display_tag)

            pygui.add_separator()
            pygui.add_text("2) Type file name")
            pygui.add_input_text(
                tag=filename_tag,
                default_value=initial_filename,
                width=-1,
            )

            pygui.add_separator()
            with pygui.group(horizontal=True):
                pygui.add_button(
                    label="Save",
                    width=340,
                    callback=lambda: self._confirm_tileset_save_path(resource, filename_tag, on_changed, editor_context, window_tag),
                )
                pygui.add_button(
                    label="Cancel",
                    width=-1,
                    callback=lambda: pygui.delete_item(window_tag),
                )

    def _draw_folder_tree(self, root_folder: str, resource: Resources.Tileset2D, editor_context: dict | None, folder_display_tag: str):
        root_folder = os.path.abspath(root_folder)
        with pygui.tree_node(label=os.path.basename(root_folder) or root_folder, default_open=True):
            pygui.add_button(
                label="Select This Folder",
                width=-1,
                callback=lambda s, a, p: self._select_save_folder(resource, p, editor_context, folder_display_tag),
                user_data=root_folder,
            )
            self._draw_folder_tree_children(root_folder, resource, editor_context, folder_display_tag)

    def _draw_folder_tree_children(self, parent_folder: str, resource: Resources.Tileset2D, editor_context: dict | None, folder_display_tag: str):
        try:
            entries = sorted(os.listdir(parent_folder))
        except Exception:
            return

        for name in entries:
            if name.startswith("."):
                continue
            full_path = os.path.join(parent_folder, name)
            if not os.path.isdir(full_path):
                continue

            with pygui.tree_node(label=name, default_open=False):
                pygui.add_button(
                    label=f"Select {name}",
                    width=-1,
                    callback=lambda s, a, p: self._select_save_folder(resource, p, editor_context, folder_display_tag),
                    user_data=full_path,
                )
                self._draw_folder_tree_children(full_path, resource, editor_context, folder_display_tag)

    def _select_save_folder(self, resource: Resources.Tileset2D, folder: str, editor_context: dict | None, folder_display_tag: str):
        folder = os.path.abspath(folder)
        setattr(resource, "_editor_save_folder", folder)

        if pygui.does_item_exist(folder_display_tag):
            pygui.set_value(folder_display_tag, self._relative_display(folder, editor_context))

    def _confirm_tileset_save_path(self, resource: Resources.Tileset2D, filename_tag: str, on_changed, editor_context: dict | None, window_tag: str):
        folder = getattr(resource, "_editor_save_folder", None)
        if not isinstance(folder, str) or not folder:
            ErrorHandler.throw_warning("Select a folder first.")
            return

        filename = ""
        if pygui.does_item_exist(filename_tag):
            try:
                filename = str(pygui.get_value(filename_tag) or "").strip()
            except Exception:
                filename = ""

        if not filename:
            ErrorHandler.throw_warning("Enter a file name.")
            return

        if not filename.lower().endswith(".tileset"):
            filename = f"{filename}.tileset"

        full_path = os.path.abspath(os.path.join(folder, filename))

        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            self._set_resource_path(resource, "resource_path", full_path, on_changed)
            resource.save(full_path)
            on_changed()
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to save tileset path: {e}")
            return

        if pygui.does_item_exist(window_tag):
            pygui.delete_item(window_tag)

    def _open_tilesheet_picker(self, resource: Resources.Tileset2D, on_changed, editor_context: dict | None):
        if not isinstance(editor_context, dict):
            return

        open_picker = editor_context.get("open_file_picker")
        if not callable(open_picker):
            return

        open_picker(
            title="Select Tilesheet",
            on_selected=lambda selected_path: self._set_tilesheet(resource, selected_path, on_changed, editor_context),
            extensions=Resources.Texture2D.extensions,
            initial_path=self._tilesheet_path(resource),
        )

    def _add_tile(self, resource: Resources.Tileset2D, on_changed):
        selected_tile = self._get_selected_tile(resource)
        new_tile = Resources.Tile2D(resource.next_available_tile_id(), name=f"Tile{resource.next_available_tile_id()}")
        new_tile.texture_region = ((0, 0), (int(resource.tile_size[0]), int(resource.tile_size[1])))
        if selected_tile is not None:
            new_tile.texture_region = selected_tile.texture_region
        resource.add_tile(new_tile)
        self._set_selected_tile_id(resource, new_tile.id)
        on_changed()

    def _remove_selected_tile(self, resource: Resources.Tileset2D, on_changed):
        selected_tile = self._get_selected_tile(resource)
        if selected_tile is None:
            return

        resource.remove_tile(selected_tile.id)
        resource.ensure_default_tile()
        self._set_selected_tile_id(resource, resource.tiles[0].id if resource.tiles else None)
        on_changed()

    def _draw_selected_tile_editor(self, resource: Resources.Tileset2D, tile: Resources.Tile2D | None, on_changed):
        if tile is None:
            pygui.add_text("No tile selected.")
            return

        pygui.add_text("Selected Tile", color=(150, 150, 150))
        pygui.add_separator()

        pygui.add_text(f"Tile ID: {tile.id}")
        pygui.add_input_text(
            label=f"##tile_name_{id(resource)}_{tile.id}",
            default_value=str(tile.name),
            width=-1,
            on_enter=True,
            callback=lambda s, v: self._set_value(tile, "name", str(v), on_changed),
        )

        pygui.add_drag_int(
            label=f"##tile_id_{id(resource)}_{tile.id}",
            default_value=int(tile.id),
            min_value=0,
            max_value=100000,
            width=-1,
            callback=lambda s, v: self._set_tile_id(resource, tile, int(v), on_changed),
        )

        pygui.add_drag_intx(
            label=f"##tile_origin_{id(resource)}_{tile.id}",
            default_value=[int(tile.texture_region[0][0]), int(tile.texture_region[0][1])],
            size=2,
            min_value=0,
            max_value=8192,
            width=-1,
            callback=lambda s, v: self._set_tile_origin(resource, tile, v, on_changed),
        )

        pygui.add_drag_intx(
            label=f"##tile_size_{id(resource)}_{tile.id}",
            default_value=[int(tile.texture_region[1][0]), int(tile.texture_region[1][1])],
            size=2,
            min_value=1,
            max_value=8192,
            width=-1,
            callback=lambda s, v: self._set_tile_region_size(resource, tile, v, on_changed),
        )

        pygui.add_text(
            f"Region: ({tile.texture_region[0][0]}, {tile.texture_region[0][1]}) / ({tile.texture_region[1][0]}, {tile.texture_region[1][1]})",
            wrap=0,
        )

        preview_surface = resource.get_tile_surface(tile.id)
        if preview_surface is not None:
            preview_tag = f"tileset_tile_preview_{id(resource)}_{tile.id}"
            self._update_texture(preview_tag, preview_surface)
            scale = min(6.0, 160.0 / max(1, max(preview_surface.get_width(), preview_surface.get_height())))
            pygui.add_spacer(height=6)
            pygui.add_text("Tile Preview", color=(140, 140, 140))
            pygui.add_image(
                preview_tag,
                width=max(1, int(preview_surface.get_width() * scale)),
                height=max(1, int(preview_surface.get_height() * scale)),
            )

    def _set_tile_id(self, resource: Resources.Tileset2D, tile: Resources.Tile2D, new_id: int, on_changed):
        new_id = max(0, int(new_id))
        existing = resource.get_tile_by_id(new_id)
        if existing is not None and existing is not tile:
            ErrorHandler.throw_warning(f"Tile ID {new_id} already exists.")
            on_changed()
            return

        tile.id = new_id
        resource.tiles.sort(key=lambda item: item.id)
        self._set_selected_tile_id(resource, tile.id)
        resource.clear_runtime_cache()
        on_changed()

    def _set_tile_origin(self, resource: Resources.Tileset2D, tile: Resources.Tile2D, value, on_changed):
        tile.texture_region = (
            (max(0, int(value[0])), max(0, int(value[1]))),
            (max(1, int(tile.texture_region[1][0])), max(1, int(tile.texture_region[1][1]))),
        )
        resource.clear_runtime_cache()
        on_changed()

    def _set_tile_region_size(self, resource: Resources.Tileset2D, tile: Resources.Tile2D, value, on_changed):
        tile.texture_region = (
            (int(tile.texture_region[0][0]), int(tile.texture_region[0][1])),
            (max(1, int(value[0])), max(1, int(value[1]))),
        )
        resource.clear_runtime_cache()
        on_changed()

    def _save_tileset(self, resource: Resources.Tileset2D, on_changed):
        if not resource.resource_path:
            ErrorHandler.throw_warning("Set a tileset path before saving.")
            return

        try:
            resource.save()
            on_changed()
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to save tileset: {e}")

    def _draw_tilesheet_preview(self, parent: str, resource: Resources.Tileset2D, selected_tile: Resources.Tile2D | None, on_changed):
        if not isinstance(resource.tilesheet, Resources.Texture2D):
            pygui.add_text("Assign a tilesheet to edit tile regions visually.", parent=parent)
            return

        sheet_surface = resource.tilesheet.get_texture()
        if sheet_surface is None:
            pygui.add_text("Failed to load the selected tilesheet.", parent=parent)
            return

        preview_tag = f"tileset_sheet_preview_{id(resource)}"
        self._update_texture(preview_tag, sheet_surface)

        max_preview_size = 420.0
        scale = min(1.0, max_preview_size / max(1, max(sheet_surface.get_width(), sheet_surface.get_height())))
        display_width = max(1, int(sheet_surface.get_width() * scale))
        display_height = max(1, int(sheet_surface.get_height() * scale))

        pygui.add_text("Tilesheet Preview", parent=parent, color=(150, 150, 150))
        if selected_tile is not None:
            pygui.add_text(
                f"Click preview to snap tile {selected_tile.id} origin to the tileset grid.",
                parent=parent,
                color=(130, 130, 130),
            )

        pygui.add_image_button(
            texture_tag=preview_tag,
            parent=parent,
            width=display_width,
            height=display_height,
            frame_padding=0,
            callback=lambda sender, app_data: self._pick_tile_origin_from_preview(sender, resource, on_changed, scale),
        )

    def _pick_tile_origin_from_preview(self, sender, resource: Resources.Tileset2D, on_changed, scale: float):
        selected_tile = self._get_selected_tile(resource)
        if selected_tile is None or not isinstance(resource.tilesheet, Resources.Texture2D):
            return

        sheet_surface = resource.tilesheet.get_texture()
        if sheet_surface is None:
            return

        mouse_x, mouse_y = pygui.get_mouse_pos(local=False)
        rect_min = pygui.get_item_rect_min(sender)
        local_x = max(0, int((mouse_x - rect_min[0]) / max(scale, 0.001)))
        local_y = max(0, int((mouse_y - rect_min[1]) / max(scale, 0.001)))

        snap_w = max(1, int(resource.tile_size[0]))
        snap_h = max(1, int(resource.tile_size[1]))
        size_w = max(1, int(selected_tile.texture_region[1][0]))
        size_h = max(1, int(selected_tile.texture_region[1][1]))

        origin_x = (local_x // snap_w) * snap_w
        origin_y = (local_y // snap_h) * snap_h
        origin_x = min(max(0, origin_x), max(0, sheet_surface.get_width() - size_w))
        origin_y = min(max(0, origin_y), max(0, sheet_surface.get_height() - size_h))

        selected_tile.texture_region = ((origin_x, origin_y), selected_tile.texture_region[1])
        resource.clear_runtime_cache()
        on_changed()

    def _ensure_texture_registry(self):
        if not pygui.does_item_exist(self._texture_registry_tag):
            with pygui.texture_registry(tag=self._texture_registry_tag, show=False):
                pass
        return self._texture_registry_tag

    def _update_texture(self, texture_tag: str, surface: pygame.Surface):
        if surface is None:
            return

        registry_tag = self._ensure_texture_registry()
        rgba = pygame.surfarray.array3d(surface).transpose((1, 0, 2))
        alpha = pygame.surfarray.array_alpha(surface).transpose((1, 0))[..., np.newaxis]
        texture_data = np.concatenate((rgba, alpha), axis=2).astype(np.float32) / 255.0

        if pygui.does_item_exist(texture_tag):
            pygui.delete_item(texture_tag)

        pygui.add_static_texture(
            width=surface.get_width(),
            height=surface.get_height(),
            default_value=texture_data.flatten().tolist(),
            tag=texture_tag,
            parent=registry_tag,
        )


def create_default_resource_registry() -> ResourceEditorRegistry:
    registry = ResourceEditorRegistry()
    registry.register(Resources.Resource, BaseResourceEditor)
    registry.register(Resources.SpriteAnimation, SpriteAnimationEditor)
    registry.register(Resources.Tileset2D, Tileset2DEditor)
    return registry

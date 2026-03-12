import dearpygui.dearpygui as pygui

from ..engine import Resources


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

    def _iter_editable_fields(self, resource: Resources.Resource):
        for attr, value in vars(resource).items():
            if attr.startswith("_"):
                continue
            if attr in self.excluded_fields:
                continue
            if callable(value):
                continue
            yield attr, value

    def draw(self, parent: str, resource: Resources.Resource, on_changed):
        with pygui.table(parent=parent, header_row=False, resizable=True):
            pygui.add_table_column(init_width_or_weight=0.35)
            pygui.add_table_column(init_width_or_weight=0.65)

            with pygui.table_row():
                pygui.add_text("Type")
                pygui.add_text(getattr(resource, "type_id", type(resource).__name__))

            with pygui.table_row():
                pygui.add_text("Path")
                pygui.add_text(str(getattr(resource, "resource_path", None) or "<Local>"))

            for attr, value in self._iter_editable_fields(resource):
                self._draw_value_row(resource, attr, value, on_changed)

    def _draw_value_row(self, resource: Resources.Resource, attr: str, value, on_changed):
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
    def draw(self, parent: str, resource: Resources.Resource, on_changed):
        if not isinstance(resource, Resources.SpriteAnimation):
            super().draw(parent, resource, on_changed)
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
                pygui.add_text(str(getattr(anim, "resource_path", None) or "<Local>"))

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
                pygui.add_input_text(
                    label=f"##sprite_anim_sheet_{id(anim)}",
                    default_value=str(anim.spritesheet_path or ""),
                    width=-1,
                    on_enter=True,
                    callback=lambda s, v: self._set_spritesheet(anim, str(v), on_changed),
                )

            with pygui.table_row():
                pygui.add_text("Frame Size")
                pygui.add_drag_intx(
                    label=f"##sprite_anim_frame_size_{id(anim)}",
                    default_value=[int(anim.frame_size[0]), int(anim.frame_size[1])],
                    size=2,
                    min_value=0,
                    max_value=8192,
                    width=-1,
                    callback=lambda s, v: self._set_frame_size(anim, v, on_changed),
                )

            with pygui.table_row():
                pygui.add_text("Frames")
                pygui.add_drag_int(
                    label=f"##sprite_anim_frames_{id(anim)}",
                    default_value=int(anim.frames),
                    min_value=0,
                    max_value=10000,
                    width=-1,
                    callback=lambda s, v: self._set_value(anim, "frames", int(v), on_changed),
                )

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
        pygui.add_button(
            parent=parent,
            label="Reload Frames",
            width=-1,
            callback=lambda: self._reload_animation(anim, on_changed),
        )

    def _set_spritesheet(self, resource: Resources.SpriteAnimation, path: str, on_changed):
        normalized = path.strip()
        if not normalized:
            resource.spritesheet_path = None
            resource.spritesheet = None
            on_changed()
            return

        resource.spritesheet_path = normalized
        resource.spritesheet = Resources.Texture2D(resource_path=normalized)
        on_changed()

    def _set_frame_size(self, resource: Resources.SpriteAnimation, value, on_changed):
        resource.frame_size = (max(0, int(value[0])), max(0, int(value[1])))
        on_changed()

    def _reload_animation(self, resource: Resources.SpriteAnimation, on_changed):
        resource.reload()
        on_changed()


def create_default_resource_registry() -> ResourceEditorRegistry:
    registry = ResourceEditorRegistry()
    registry.register(Resources.Resource, BaseResourceEditor)
    registry.register(Resources.SpriteAnimation, SpriteAnimationEditor)
    return registry

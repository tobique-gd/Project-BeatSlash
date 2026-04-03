import dearpygui.dearpygui as pygui
import numpy as np
import pygame
import os
from typing import Any, Callable
from ...engine import ErrorHandler
from ...engine import Nodes
from ...engine import ResourceServer
from ...engine import Resources
from ...engine.Resources import Resource, CollisionRectangleShape
from ..ResourceEditors import create_default_resource_registry
from .FileSystem import ignored_directory_list, ignored_file_list


class InspectorPanel:
    _texture_registry_tag = "inspector_texture_registry"

    def __init__(self, ui):
        self.ui = ui
        self._resource_registry = create_default_resource_registry()
        self._file_picker_state: dict[str, Any] = {
            "on_selected": None,
            "extensions": None,
        }
        self._resource_slot_registry: dict[type, dict[str, type[Resource]]] = {
            Nodes.Node: {"script": Resource},
            Nodes.Sprite2D: {"texture": Resource},
            Nodes.AnimatedSprite2D: {"current_animation": Resource},
            Nodes.AudioPlayer: {"audio": Resource},
            Nodes.TileMap2D: {"tileset": Resources.Tileset2D},
        }
        self._custom_property_editors: dict[tuple[type, str], Callable[[object, str, object, str], None]] = {
            (Nodes.AnimatedSprite2D, "animations"): self._draw_animations_property,
        }

    def _resource_slot_info(self, node, attr, value):
        if isinstance(value, Resource):
            return True, value

        for cls in type(node).mro():
            attr_map = self._resource_slot_registry.get(cls)
            if attr_map and attr in attr_map:
                return True, None

        backing_candidates = [f"_{attr}_resource", f"_{attr}"]
        for backing_name in backing_candidates:
            if not hasattr(node, backing_name):
                continue

            backing_value = getattr(node, backing_name)
            if isinstance(backing_value, Resource):
                return True, backing_value
            if backing_value is None and isinstance(getattr(type(node), attr, None), property):
                return True, None

        return False, None

    def _resource_display_value(self, value):
        if value is None:
            return "None"

        path_value = None
        for field in ("resource_path", "texture_path", "file_path", "script_path"):
            candidate = getattr(value, field, None)
            if isinstance(candidate, str) and candidate:
                path_value = candidate
                break

        if path_value:
            display_value = self.ui.editor.to_relative_path(path_value)
        elif hasattr(value, "name") and getattr(value, "name"):
            display_value = str(value.name)
        else:
            display_value = str(value)

        if len(display_value) > 30:
            display_value = "..." + display_value[-27:]
        return display_value

    def _from_relative_path(self, path_str):
        if not isinstance(path_str, str) or not path_str:
            return path_str
            
        try:
            if os.path.isabs(path_str):
                return path_str
                
            project_directory = self.ui.editor.settings.project_settings["file_management"]["project_directory"]
            return os.path.abspath(os.path.join(project_directory, path_str))
        except Exception:
            return path_str

    def build(self):
        pygui.add_text("Inspector", color=(150, 150, 150))
        pygui.add_separator()

    def update(self, node):
        pygui.delete_item("inspector_panel", children_only=True)

        if node is None:
            pygui.add_text("Inspector", parent="inspector_panel", color=(150, 150, 150))
            pygui.add_separator(parent="inspector_panel")
            return

        if not hasattr(node, "__dict__"):
            pygui.add_text("Inspector", parent="inspector_panel", color=(150, 150, 150))
            pygui.add_separator(parent="inspector_panel")
            node_type = type(node).__name__
            pygui.add_text(f"Unsupported selection type: {node_type}", parent="inspector_panel", color=(180, 120, 120))
            return


        pygui.add_text("Inspector", parent="inspector_panel", color=(150, 150, 150))
        pygui.add_separator(parent="inspector_panel")

        with pygui.table(parent="inspector_panel", header_row=False, resizable=True):
            pygui.add_table_column(init_width_or_weight=0.35)
            pygui.add_table_column(init_width_or_weight=0.65)
            
            with pygui.table_row():
                pygui.add_text("Type")
                pygui.add_button(
                    label=type(node).__name__,
                    width=-1,
                    callback=self.ui.dialogs.show_change_type_window
                )

            self.draw_property(node, "name", getattr(node, "name", ""))

        excluded = {"_children", "_parent", "runtime_script", "name", "global_position", "is_linked_scene", "linked_scene_path"}
        node_cls = type(node)
        mro = [cls for cls in node_cls.mro() if cls is not object]
        base_to_derived = list(reversed(mro))

        instance_items = []
        for attr, value in vars(node).items():
            if attr.startswith("_"):
                continue
            if attr in excluded:
                continue
            if callable(value):
                continue
            instance_items.append((attr, value))

        instance_order = {attr: index for index, (attr, _) in enumerate(instance_items)}

        instance_keys_by_class = {}
        for cls in base_to_derived:
            try:
                probe = cls()
                keys = {
                    key for key, value in vars(probe).items()
                    if not key.startswith("_") and key not in excluded and not callable(value)
                }
            except Exception:
                keys = set()
            instance_keys_by_class[cls] = keys

        introduced_by_class = {}
        cumulative = set()
        for cls in base_to_derived:
            keys = instance_keys_by_class.get(cls, set())
            introduced = keys - cumulative
            introduced_by_class[cls] = introduced
            cumulative |= keys

        property_owner = {}
        for cls in mro:
            for prop_name, descriptor in cls.__dict__.items():
                if not isinstance(descriptor, property):
                    continue
                if descriptor.fset is None:
                    continue
                if prop_name in excluded:
                    continue
                if prop_name not in property_owner:
                    property_owner[prop_name] = cls

        groups = {cls: [] for cls in mro}

        for attr, value in instance_items:
            owner = None
            for cls in base_to_derived:
                if attr in introduced_by_class.get(cls, set()):
                    owner = cls
            if owner is None:
                owner = node_cls
            groups.setdefault(owner, []).append((attr, value, instance_order.get(attr, 9999)))

        for prop_name, owner in property_owner.items():
            if any(existing_attr == prop_name for existing_attr, _ in instance_items):
                continue
            try:
                value = getattr(node, prop_name)
            except Exception:
                continue
            if callable(value):
                continue
            groups.setdefault(owner, []).append((prop_name, value, 10000 + len(groups.get(owner, []))))

        first_group = True
        for cls in mro:
            items = groups.get(cls, [])
            if not items:
                continue

            if not first_group:
                pygui.add_separator(parent="inspector_panel")
            first_group = False

            pygui.add_text(f"{cls.__name__}", parent="inspector_panel", color=(130, 130, 130))

            items = sorted(items, key=lambda item: item[2])
            with pygui.table(parent="inspector_panel", header_row=False, resizable=True):
                pygui.add_table_column(init_width_or_weight=0.35)
                pygui.add_table_column(init_width_or_weight=0.65)

                for attr, value, _ in items:
                    self.draw_property(node, attr, value)

        if isinstance(node, Nodes.TileMap2D):
            self._draw_tilemap_palette(node)


    def draw_property(self, node, attr, value):
        FLOAT_MIN = -1000000.0
        FLOAT_MAX = 1000000.0
        INT_MIN = -1000000
        INT_MAX = 1000000
        label_text = attr.replace("_", " ").title()

        for cls in type(node).mro():
            editor = self._custom_property_editors.get((cls, attr))
            if editor is not None:
                editor(node, attr, value, label_text)
                return

        is_resource_slot, resource_value = self._resource_slot_info(node, attr, value)
        if is_resource_slot:
            with pygui.table_row():
                pygui.add_text(label_text)
                button_tag = f"resource_btn_{id(node)}_{attr}"
                display_value = self._resource_display_value(resource_value)
                
                pygui.add_button(
                    label=display_value,
                    tag=button_tag,
                    width=-1,
                    callback=self._open_resource_editor,
                    user_data=(node, attr),
                    drop_callback=self._drop_resource_file,
                    payload_type="file_payload"
                )
            return

        if isinstance(value, str):
            display_value = self.ui.editor.to_relative_path(value)

            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_input_text(
                    label=f"##{attr}",
                    default_value=display_value,
                    width=-1,
                    on_enter=True,
                    user_data=(node, attr),
                    drop_callback=self._drop_resource_file,
                    payload_type="file_payload",
                    callback=lambda s, a: setattr(
                        node,
                        attr,
                        self._from_relative_path(a)
                    ),
                )

            return

        if isinstance(value, bool):
            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_checkbox(
                    label=f"##{attr}",
                    default_value=value,
                    callback=lambda s, v: setattr(node, attr, v)
                )
            return

        if isinstance(value, int):
            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_drag_int(
                    label=f"##{attr}",
                    default_value=value,
                    min_value=INT_MIN,
                    max_value=INT_MAX,
                    width=-1,
                    callback=lambda s, v: setattr(node, attr, int(v))
                )
            return

        if isinstance(value, float):
            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_drag_float(
                    label=f"##{attr}",
                    default_value=value,
                    min_value=FLOAT_MIN,
                    max_value=FLOAT_MAX,
                    width=-1,
                    callback=lambda s, v: setattr(node, attr, float(v))
                )
            return

        if isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
            float_list = [float(value[0]), float(value[1])]
            with pygui.table_row():
                pygui.add_text(label_text)
                pygui.add_drag_floatx(
                    label=f"##{attr}",
                    default_value=float_list,
                    size=2,
                    speed=0.1,
                    min_value=FLOAT_MIN,
                    max_value=FLOAT_MAX,
                    width=-1,
                    callback=lambda s, v: setattr(node, attr, (v[0], v[1]))
                )
            return

        with pygui.table_row():
            pygui.add_text(label_text)
            pygui.add_text(str(value))
            

    def _draw_collision_shape_editor(self, node, attr, value):
        resource_path = getattr(value, "resource_path", None)
        display_path = self.ui.editor.to_relative_path(resource_path) if resource_path else "<Local>"
        
        with pygui.table_row():
            pygui.add_text("Resource")
            pygui.add_button(
                label=display_path, 
                width=-1, 
                user_data=(node, attr),
                drop_callback=self._drop_resource_file
            )

        current_type = "RECTANGLE"
        
        with pygui.table_row():
            pygui.add_text("Shape Type")
            pygui.add_combo(
                items=["RECTANGLE"],
                default_value=current_type,
                width=-1,
                user_data=(node, attr),
                callback=self._on_shape_type_changed
            )

        if isinstance(value, CollisionRectangleShape):
            with pygui.table_row():
                pygui.add_text("Size")
                pygui.add_drag_floatx(
                    label="##size",
                    default_value=list(value.size),
                    size=2,
                    speed=1.0,
                    width=-1,
                    callback=lambda s, v: setattr(value, "size", tuple(v))
                )

    def _draw_tilemap_palette(self, node: Nodes.TileMap2D):
        pygui.add_separator(parent="inspector_panel")
        pygui.add_text("Tile Palette", parent="inspector_panel", color=(130, 130, 130))

        tileset = getattr(node, "tileset", None)
        if not isinstance(tileset, Resources.Tileset2D):
            pygui.add_text("Assign a Tileset resource to view available tiles.", parent="inspector_panel")
            return

        tileset.ensure_default_tile()
        selected_tile_id = self._get_selected_tilemap_tile_id(node, tileset)
        selected_layer_index = self._get_selected_tilemap_layer_index(node)
        pygui.add_text(f"Selected Tile ID: {selected_tile_id}", parent="inspector_panel", color=(150, 150, 150))

        with pygui.group(parent="inspector_panel", horizontal=True):
            pygui.add_text("Paint Layer")
            pygui.add_input_int(
                label=f"##tilemap_layer_input_{id(node)}",
                default_value=int(selected_layer_index),
                step=1,
                step_fast=5,
                width=120,
                user_data=node,
                callback=self._on_tilemap_layer_input_changed,
            )

        list_tag = f"tilemap_palette_list_{id(node)}"
        with pygui.child_window(parent="inspector_panel", tag=list_tag, border=True, height=240):
            for tile in tileset.tiles:
                surface = tileset.get_tile_surface(tile.id)
                preview_tag = None
                if surface is not None:
                    preview_tag = f"tilemap_palette_preview_{id(node)}_{tile.id}"
                    self._update_texture(preview_tag, surface)

                with pygui.group(horizontal=True):
                    if preview_tag is not None and surface is not None and pygui.does_item_exist(preview_tag):
                        thumb = max(12, min(32, max(surface.get_width(), surface.get_height())))
                        pygui.add_image(preview_tag, width=thumb, height=thumb)
                    else:
                        pygui.add_text("[ ]")

                    label = f"{tile.id}: {tile.name}"
                    if int(tile.id) == int(selected_tile_id):
                        label = f"> {label}"

                    pygui.add_button(
                        label=label,
                        width=-1,
                        callback=lambda *_, tile_id=tile.id: self._select_tilemap_palette_tile(node, int(tile_id)),
                    )

    def _get_selected_tilemap_tile_id(self, node: Nodes.TileMap2D, tileset: Resources.Tileset2D):
        selected_id = self.ui.editor.get_selected_paint_tile_id(node)
        if isinstance(selected_id, int) and tileset.get_tile_by_id(selected_id) is not None:
            return selected_id

        fallback_tile = tileset.tiles[0] if tileset.tiles else None
        fallback_id = int(fallback_tile.id) if fallback_tile is not None else 0
        self.ui.editor.set_selected_paint_tile_id(node, fallback_id)
        return fallback_id

    def _select_tilemap_palette_tile(self, node: Nodes.TileMap2D, tile_id: int):
        self.ui.editor.set_selected_paint_tile_id(node, int(tile_id))
        self.update(node)

    def _get_selected_tilemap_layer_index(self, node: Nodes.TileMap2D) -> int:
        selected_layer = self.ui.editor.get_selected_paint_tile_layer(node)
        try:
            return int(selected_layer)
        except Exception:
            self.ui.editor.set_selected_paint_tile_layer(node, 0)
            return 0

    def _set_tilemap_layer_index(self, node: Nodes.TileMap2D, layer_index):
        if node is None:
            return

        try:
            normalized_layer = int(layer_index)
        except Exception:
            normalized_layer = 0

        self.ui.editor.set_selected_paint_tile_layer(node, normalized_layer)
        self.update(node)

    def _on_tilemap_layer_input_changed(self, sender, app_data, user_data):
        self._set_tilemap_layer_index(user_data, app_data)

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

    def _on_shape_type_changed(self, sender, new_type, user_data):
        node, attr = user_data
        try:
            if new_type == "RECTANGLE":
                new_shape = CollisionRectangleShape(size=(32, 32))
            setattr(node, attr, new_shape)
            
            self.update(node)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to change shape: {e}")

    def clear(self):
        pygui.delete_item("inspector_panel", children_only=True)
        pygui.add_text("Inspector", parent="inspector_panel", color=(150, 150, 150))
        pygui.add_separator(parent="inspector_panel")

    def _resource_classes(self):
        classes = set()
        for cls in Resource._type_registry.values():
            if isinstance(cls, type) and issubclass(cls, Resource) and cls is not Resource:
                classes.add(cls)
        return sorted(classes, key=lambda c: c.__name__)

    def _resource_slot_class(self, node, attr):
        for cls in type(node).mro():
            attr_map = self._resource_slot_registry.get(cls)
            if attr_map and attr in attr_map:
                resource_cls = attr_map[attr]
                if isinstance(resource_cls, type) and issubclass(resource_cls, Resource):
                    return resource_cls
                return Resource
        return Resource

    def _resource_classes_for_slot(self, node, attr):
        slot_cls = self._resource_slot_class(node, attr)
        return [cls for cls in self._resource_classes() if issubclass(cls, slot_cls)]

    def _open_resource_editor(self, sender, app_data, user_data):
        node, attr = user_data
        self._show_resource_editor_window(node, attr)

    def _draw_animations_property(self, node, attr, value, label_text):
        count = len(value) if isinstance(value, list) else 0
        with pygui.table_row():
            pygui.add_text(label_text)
            pygui.add_button(
                label=f"Manage ({count})",
                width=-1,
                callback=lambda: self._show_animations_window(node),
            )

    def _show_animations_window(self, node):
        window_tag = f"animations_editor_{id(node)}"
        content_tag = f"animations_editor_content_{id(node)}"

        if not pygui.does_item_exist(window_tag):
            with pygui.window(
                label="Animations",
                tag=window_tag,
                width=560,
                height=520,
                no_collapse=True,
            ):
                with pygui.child_window(tag=content_tag, border=False):
                    pass

        self._render_animations_content(node, content_tag)
        pygui.show_item(window_tag)

    def _render_animations_content(self, node, parent_tag):
        if not pygui.does_item_exist(parent_tag):
            return

        pygui.delete_item(parent_tag, children_only=True)

        animations = getattr(node, "animations", None)
        if not isinstance(animations, list):
            pygui.add_text("This node has no animations list.", parent=parent_tag)
            return

        pygui.add_text("AnimatedSprite2D Animations", parent=parent_tag, color=(140, 140, 140))
        pygui.add_separator(parent=parent_tag)

        pygui.add_button(
            parent=parent_tag,
            label="Add New Animation",
            width=-1,
            callback=lambda: self._add_animation(node, parent_tag),
        )
        pygui.add_separator(parent=parent_tag)

        for index, anim in enumerate(animations):
            name = getattr(anim, "name", f"Animation {index}")
            current = getattr(node, "current_animation", None)
            is_current = current is anim
            label = f"{index}: {name}{' (Current)' if is_current else ''}"

            with pygui.group(parent=parent_tag):
                pygui.add_text(label)
                with pygui.group(horizontal=True):
                    pygui.add_button(
                        label=f"Edit##anim_edit_{id(node)}_{index}",
                        width=180,
                        user_data=(node, index, parent_tag),
                        callback=self._on_edit_animation_clicked,
                    )
                    pygui.add_button(
                        label=f"Set Current##anim_set_{id(node)}_{index}",
                        width=180,
                        user_data=(node, index, parent_tag),
                        callback=self._on_set_current_animation_clicked,
                    )
                    pygui.add_button(
                        label=f"Remove##anim_remove_{id(node)}_{index}",
                        width=180,
                        user_data=(node, index, parent_tag),
                        callback=self._on_remove_animation_clicked,
                    )
                pygui.add_separator()

    def _on_edit_animation_clicked(self, sender, app_data, user_data):
        node, index, parent_tag = user_data
        self._open_animation_resource_editor(node, index, parent_tag)

    def _on_set_current_animation_clicked(self, sender, app_data, user_data):
        node, index, parent_tag = user_data
        self._set_current_animation_by_index(node, index, parent_tag)

    def _on_remove_animation_clicked(self, sender, app_data, user_data):
        node, index, parent_tag = user_data
        self._remove_animation_by_index(node, index, parent_tag)

    def _add_animation(self, node, parent_tag):
        try:
            from ...engine import Resources as EngineResources
            animation = EngineResources.SpriteAnimation(name=f"Animation{len(node.animations)}")

            template = node.current_animation
            if template is None and node.animations:
                template = node.animations[0]

            if isinstance(template, EngineResources.SpriteAnimation):
                animation.frame_size = tuple(template.frame_size)
                animation.fps = int(template.fps)
                animation.loop = bool(template.loop)
                if getattr(template, "spritesheet_path", None):
                    animation.spritesheet_path = template.spritesheet_path
                    animation.spritesheet = EngineResources.Texture2D(resource_path=template.spritesheet_path)
                animation.reload()

            node.add_animation(animation)
            if node.current_animation is None:
                node.current_animation = animation
            self.update(node)
            self._render_animations_content(node, parent_tag)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to add animation: {e}")

    def _set_current_animation_by_index(self, node, index, parent_tag):
        try:
            if index < 0 or index >= len(node.animations):
                return
            node.current_animation = node.animations[index]
            self.update(node)
            self._render_animations_content(node, parent_tag)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to set current animation: {e}")

    def _remove_animation_by_index(self, node, index, parent_tag):
        try:
            if index < 0 or index >= len(node.animations):
                return
            removed = node.animations.pop(index)
            if node.current_animation is removed:
                node.current_animation = node.animations[0] if node.animations else None
            self.update(node)
            self._render_animations_content(node, parent_tag)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to remove animation: {e}")

    def _open_animation_resource_editor(self, node, index, parent_tag):
        if index < 0 or index >= len(node.animations):
            return
        attr = "current_animation"
        node.current_animation = node.animations[index]
        self._show_resource_editor_window(node, attr)
        self._render_animations_content(node, parent_tag)

    def _show_resource_editor_window(self, node, attr):
        window_tag = f"resource_editor_{id(node)}_{attr}"
        content_tag = f"resource_editor_content_{id(node)}_{attr}"

        if not pygui.does_item_exist(window_tag):
            with pygui.window(
                label=f"Edit {attr}",
                tag=window_tag,
                width=520,
                height=500,
                no_collapse=True,
            ):
                with pygui.child_window(tag=content_tag, border=False):
                    pass

        self._render_resource_editor_content(node, attr, content_tag)
        pygui.show_item(window_tag)

    def _render_resource_editor_content(self, node, attr, parent_tag):
        if not pygui.does_item_exist(parent_tag):
            return

        pygui.delete_item(parent_tag, children_only=True)

        try:
            current_value = getattr(node, attr)
        except Exception:
            current_value = None

        is_resource_slot, resource_value = self._resource_slot_info(node, attr, current_value)
        if not is_resource_slot:
            pygui.add_text("This field is not a resource slot.", parent=parent_tag)
            return

        pygui.add_text(f"Property: {attr}", parent=parent_tag, color=(140, 140, 140))
        pygui.add_separator(parent=parent_tag)

        if resource_value is None:
            classes = self._resource_classes_for_slot(node, attr)
            class_names = [cls.__name__ for cls in classes]

            if not class_names:
                pygui.add_text("No resource classes registered.", parent=parent_tag)
                return

            default_name = class_names[0]

            with pygui.group(parent=parent_tag):
                pygui.add_text("Create Resource", color=(160, 160, 160))
                selector_tag = f"resource_type_selector_{id(node)}_{attr}"
                pygui.add_combo(
                    items=class_names,
                    default_value=default_name,
                    tag=selector_tag,
                    width=-1,
                )
                pygui.add_button(
                    label="Create",
                    width=-1,
                    callback=lambda: self._create_resource_for_slot(node, attr, classes, selector_tag, parent_tag),
                )

            return

        editor = self._resource_registry.get_editor(resource_value)
        editor.draw(
            parent=parent_tag,
            resource=resource_value,
            on_changed=lambda: self._on_resource_changed(node, attr, parent_tag),
            editor_context={
                "to_relative_path": self.ui.editor.to_relative_path,
                "from_relative_path": self._from_relative_path,
                "open_file_picker": self._show_project_file_picker,
            },
        )

        pygui.add_separator(parent=parent_tag)
        with pygui.group(parent=parent_tag, horizontal=True):
            pygui.add_button(
                label="Apply",
                width=250,
                callback=lambda: self._apply_resource_changes(node, attr, resource_value),
            )
            pygui.add_button(
                label="Clear",
                width=250,
                callback=lambda: self._clear_resource_slot(node, attr, parent_tag),
            )

    def _create_resource_for_slot(self, node, attr, classes, selector_tag, parent_tag):
        selected_name = pygui.get_value(selector_tag)
        selected_cls = None
        for cls in classes:
            if cls.__name__ == selected_name:
                selected_cls = cls
                break

        if selected_cls is None:
            ErrorHandler.throw_error("Could not resolve selected resource type")
            return

        try:
            resource_obj = selected_cls()
            setattr(node, attr, resource_obj)
            self.update(node)
            self._render_resource_editor_content(node, attr, parent_tag)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to create resource: {e}")

    def _apply_resource_changes(self, node, attr, resource_value):
        try:
            setattr(node, attr, resource_value)
            
            self.update(node)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed applying resource changes: {e}")

    def _clear_resource_slot(self, node, attr, parent_tag):
        try:
            setattr(node, attr, None)
            
            self.update(node)
            self._render_resource_editor_content(node, attr, parent_tag)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed clearing resource slot: {e}")

    def _on_resource_changed(self, node, attr, parent_tag):
        self.update(node)
        self._render_resource_editor_content(node, attr, parent_tag)

        # Refresh animation management window if open
        animations_content_tag = f"animations_editor_content_{id(node)}"
        if pygui.does_item_exist(animations_content_tag):
            self._render_animations_content(node, animations_content_tag)

    def _show_project_file_picker(self, title, on_selected, extensions=None, initial_path=None):
        if not callable(on_selected):
            return

        window_tag = "inspector_resource_file_picker"
        tree_tag = "inspector_resource_file_picker_tree"
        project_directory = self.ui.editor.settings.project_settings["file_management"]["project_directory"]

        normalized_extensions = None
        if isinstance(extensions, (tuple, list)) and extensions:
            normalized_extensions = tuple(str(ext).lower() for ext in extensions if isinstance(ext, str) and ext)

        self._file_picker_state["on_selected"] = on_selected
        self._file_picker_state["extensions"] = normalized_extensions

        if pygui.does_item_exist(window_tag):
            pygui.delete_item(window_tag)

        with pygui.window(
            label=title or "Select File",
            tag=window_tag,
            width=620,
            height=520,
            no_collapse=True,
            modal=False,
        ):
            pygui.add_text("Project Files", color=(150, 150, 150))
            pygui.add_separator()
            with pygui.child_window(tag=tree_tag, border=True, height=-52):
                self._build_picker_tree(project_directory)

            pygui.add_separator()
            with pygui.group(horizontal=True):
                pygui.add_button(
                    label="Cancel",
                    width=-1,
                    callback=lambda: pygui.delete_item(window_tag),
                )

        main_width = pygui.get_item_width("Primary Window") or 1400
        main_height = pygui.get_item_height("Primary Window") or 900
        picker_x = int((main_width / 2 - 620 / 2))
        picker_y = int((main_height / 2 - 520 / 2))
        pygui.set_item_pos(window_tag, [picker_x, picker_y])

    def _build_picker_tree(self, path):
        try:
            items = sorted(os.listdir(path))
            for item in items:
                if item.startswith(".") or item in ignored_file_list or item in ignored_directory_list:
                    continue

                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    with pygui.tree_node(label=item, default_open=False):
                        self._build_picker_tree(full_path)
                    continue

                if not self._matches_picker_extensions(full_path):
                    continue

                pygui.add_selectable(
                    label=item,
                    user_data=full_path,
                    callback=self._on_picker_file_selected,
                    span_columns=True,
                )
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to build file picker: {e}")

    def _matches_picker_extensions(self, full_path: str):
        extensions = self._file_picker_state.get("extensions")
        if not extensions:
            return True

        _, ext = os.path.splitext(full_path)
        return ext.lower() in extensions

    def _on_picker_file_selected(self, sender, app_data, user_data):
        selected_path = user_data
        callback = self._file_picker_state.get("on_selected")
        if not callable(callback):
            return

        try:
            callback(selected_path)
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to set selected file: {e}")
            return

        if pygui.does_item_exist("inspector_resource_file_picker"):
            pygui.delete_item("inspector_resource_file_picker")

    def _drop_resource_file(self, sender, app_data, user_data):
        try:
            button_user_data = pygui.get_item_user_data(sender)
            if button_user_data is None:
                ErrorHandler.throw_error("No user data found on button")
                return
            
            node, attr = button_user_data
    
            file_path = app_data
            if file_path is None or not isinstance(file_path, str):
                ErrorHandler.throw_error("No valid file path in drop event")
                return

            is_resource_slot, _ = self._resource_slot_info(node, attr, getattr(node, attr, None))
            if is_resource_slot:
                slot_cls = self._resource_slot_class(node, attr)
                resource_value = ResourceServer.ResourceLoader.load(file_path)

                if resource_value is None and isinstance(slot_cls, type) and issubclass(slot_cls, Resource):
                    try:
                        resource_value = slot_cls.from_path(file_path)
                    except Exception:
                        resource_value = None

                if resource_value is None:
                    ErrorHandler.throw_error(f"Failed to load resource from {file_path}")
                    return

                if slot_cls is not Resource and not isinstance(resource_value, slot_cls):
                    ErrorHandler.throw_error(f"{attr} expects {slot_cls.__name__}, got {type(resource_value).__name__}")
                    return

                setattr(node, attr, resource_value)
                self.update(node)
                return
            
            try:
                setattr(node, attr, file_path)
                self.update(node)
            except Exception as e:
                ErrorHandler.throw_error(f"Failed to set {attr}: {e}")
                
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to process dropped file: {e}")

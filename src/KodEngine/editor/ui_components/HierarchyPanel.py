import dearpygui.dearpygui as pygui
import pygame
import numpy as np

class HierarchyPanel:
    def __init__(self, ui):
        self.ui = ui

    def _is_descendant_of(self, node, potential_ancestor):
        current = getattr(node, "_parent", None)
        while current is not None:
            if current is potential_ancestor:
                return True
            current = getattr(current, "_parent", None)
        return False

    
    def build(self):
        pygui.add_text("Hierarchy", color=(150, 150, 150))
        pygui.add_separator()
        with pygui.table(header_row=False, resizable=False):
            pygui.add_table_column(init_width_or_weight=0.2)
            pygui.add_table_column(init_width_or_weight=0.2)
            pygui.add_table_column(init_width_or_weight=0.6)

            with pygui.table_row():
                #TODO: use textures instead of words
                pygui.add_button(label="Add", tag="add_node_btn", width=-1, callback=self.ui.dialogs.show_add_node_window)
                pygui.add_button(label="Del", tag="delete_node_btn", width=-1, callback=self.ui.dialogs.show_delete_node_window)
                
        pygui.add_separator()
        with pygui.group(tag="hierarchy_tree"):
            self.draw_tree(self.ui.editor.get_scene_hierarchy())

    def draw_tree(self, tree, _parent=None):
        for node, _children in tree.items():
            if _children:
                with pygui.tree_node(label=node.name, default_open=True):
                    self.add_node_selectable(node)
                    self.draw_tree(_children, _parent=None)
            else:
                self.add_node_selectable(node, _parent=_parent)

    def add_node_selectable(self, node, _parent=None):
        tag = f"select_{id(node)}"

        self.ui.state.selectables[tag] = node

        kwargs = {
            "label": node.name,
            "tag": tag,
            "callback": self.on_node_selected,
            "user_data": node,
            "drag_callback": self._on_node_drag,
            "drop_callback": self._on_node_drop,
            "payload_type": "node_payload",
            "user_data": node,
 
        }
        if _parent is not None:
            kwargs["parent"] = _parent

        pygui.add_selectable(**kwargs)
        
        with pygui.drag_payload(parent=tag, drag_data=tag, payload_type="node_payload"):
            pygui.add_text(f"Drag {node.name}")

    def on_node_selected(self, sender, app_data):
        node = self.ui.state.selectables[sender]

        for tag in list(self.ui.state.selectables.keys()):
            if pygui.does_item_exist(tag):
                pygui.set_value(tag, False)

        pygui.set_value(sender, True)

        self.ui.state.selected_node = node
        self.ui.inspector.update(node)
        
        if pygui.does_item_exist("add_node_btn"):
            pygui.configure_item("add_node_btn", enabled=True)

    def _on_node_drop(self, sender, app_data, user_data):
        payload_tag = app_data
        if isinstance(app_data, dict) and "data" in app_data:
            payload_tag = app_data.get("data")

        dragged_node = self.ui.state.selectables.get(payload_tag)
        target_node = self.ui.state.selectables.get(sender)

        if dragged_node is None or target_node is None:
            return

        if dragged_node is target_node:
            return

        if getattr(dragged_node, "_parent", None) is None:
            return

        if self._is_descendant_of(target_node, dragged_node):
            return

        old_parent = getattr(dragged_node, "_parent", None)
        if old_parent is target_node:
            return

        old_global_position = getattr(dragged_node, "global_position", None)
        dragged_node.reparent_to(target_node)

        if old_global_position is not None:
            try:
                dragged_node.global_position = old_global_position
            except Exception:
                pass

        self.update_hierarchy()
        self.ui.editor._set_selected_node(dragged_node)

    def _on_node_drag(self, sender, app_data, user_data):
        pass

    def update_hierarchy(self):
        if pygui.does_item_exist("hierarchy_tree"):
            pygui.delete_item("hierarchy_tree", children_only=True)
            self.ui.state.selectables = {}
            with pygui.group(parent="hierarchy_tree"):
                self.draw_tree(self.ui.editor.get_scene_hierarchy())

        if self.ui.state.selected_node:
            selected_tag = f"select_{id(self.ui.state.selected_node)}"
            if not pygui.does_item_exist(selected_tag):
                self.ui.state.selected_node = None
                self.ui.inspector.clear()
                if pygui.does_item_exist("add_node_btn"):
                    pygui.configure_item("add_node_btn", enabled=False)


import dearpygui.dearpygui as pygui
import pygame
import numpy as np

class HierarchyPanel:
    def __init__(self, ui):
        self.ui = ui

    
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
            "drag_callback": self._on_node_drag
        }
        if _parent is not None:
            kwargs["parent"] = _parent

        pygui.add_selectable(**kwargs)
        
        with pygui.drag_payload(parent=tag, drag_data=tag, payload_type="collision_shape_payload"):
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

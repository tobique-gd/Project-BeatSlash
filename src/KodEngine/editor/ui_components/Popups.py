import dearpygui.dearpygui as pygui
from ...engine import Nodes
from ...engine.ErrorHandler import ErrorHandler

class NodeDialogs:
    def __init__(self, ui):
        self.ui = ui

    def get_node_classes(self):
        node_classes = []
        for attr_name in dir(Nodes):
            attr = getattr(Nodes, attr_name)
            if isinstance(attr, type) and issubclass(attr, Nodes.Node) and attr is not Nodes.Node:
                node_classes.append((attr_name, attr))
        return sorted(node_classes, key=lambda x: x[0])

    def show_delete_node_window(self, sender, app_data):
        if not self.ui.state.selected_node:
            return

        if pygui.does_item_exist("delete_node_window"):
            pygui.delete_item("delete_node_window")
        
        with pygui.window(label="Delete Node", tag="delete_node_window", modal=True, show=True, width=300, height=80, no_resize=True):
            pygui.add_text(f"Do you really want to delete '{self.ui.state.selected_node.name}'?")
            pygui.add_separator()
            with pygui.group(horizontal=True):
                pygui.add_button(label="Delete", width=140, callback=self.delete_selected_node)
                pygui.add_button(label="Cancel", width=140, callback=lambda: pygui.delete_item("delete_node_window"))
        
        main_width = pygui.get_item_width("Primary Window") or 1920
        main_height = pygui.get_item_height("Primary Window") or 1080
        modal_x = int((main_width / 2 - 300 / 2))
        modal_y = int((main_height / 2 - 80 / 2))
        pygui.set_item_pos("delete_node_window", [modal_x, modal_y])

    def delete_selected_node(self, sender=None, app_data=None):
        if not self.ui.state.selected_node:
            return
        
        if self.ui.state.selected_node == self.ui.editor.root:
            ErrorHandler.throw_warning("Cannot delete root node")
            if pygui.does_item_exist("delete_node_window"):
                pygui.delete_item("delete_node_window")
            return
        
        try:
            self.ui.state.selected_node.queue_free()
        except Exception as e:
            ErrorHandler.throw_error(f"Error deleting node: {e}")
        
        if pygui.does_item_exist("delete_node_window"):
            pygui.delete_item("delete_node_window")

    def show_add_node_window(self, sender, app_data):
        if not self.ui.state.selected_node:
            return
        
        if pygui.does_item_exist("add_node_window"):
            pygui.delete_item("add_node_window")

        modal_width = 300
        modal_height = 400
        
        with pygui.window(label="Add Node", tag="add_node_window", modal=True, show=True, width=modal_width, height=modal_height):
            pygui.add_text("Select a node type to add:")
            pygui.add_separator()

            node_classes = self.get_node_classes()

            for node_name, node_class in node_classes:
                pygui.add_button(
                    label=node_name,
                    width=-1,
                    user_data=node_class,
                    callback=self.on_node_type_selected
                )
        
        main_width = pygui.get_item_width("Primary Window") or 1400
        main_height = pygui.get_item_height("Primary Window") or 900
        modal_x = int((main_width / 2 - modal_width / 2))
        modal_y = int((main_height / 2 - modal_height / 2))
        pygui.set_item_pos("add_node_window", [modal_x, modal_y])

    def on_node_type_selected(self, sender, app_data, user_data):
        if not self.ui.state.selected_node:
            ErrorHandler.throw_warning("No node selected to add child to")
            return

        node_class = user_data
        try:
            new_node = node_class()
            self.ui.state.selected_node.add_child(new_node)
            self.ui.hierarchy.update_hierarchy()
            ErrorHandler.throw_success(f"Created node '{node_class.__name__}' successfully")
            
            if pygui.does_item_exist("add_node_window"):
                pygui.delete_item("add_node_window")
        except Exception as e:
            ErrorHandler.throw_error(f"Error creating node: {e}")

    def show_change_type_window(self, sender, app_data):
        if not self.ui.state.selected_node:
            return
        
        if pygui.does_item_exist("change_type_window"):
            pygui.delete_item("change_type_window")

        modal_width = 300
        modal_height = 400
        current_type = type(self.ui.state.selected_node).__name__
        
        with pygui.window(label="Change Node Type", tag="change_type_window", modal=True, show=True, width=modal_width, height=modal_height):
            pygui.add_text(f"Current type: {current_type}")
            pygui.add_text("Select new type:")
            pygui.add_separator()

            node_classes = self.get_node_classes()

            for node_name, node_class in node_classes:
                pygui.add_button(
                    label=node_name,
                    width=-1,
                    user_data=node_class,
                    callback=self.on_change_type_selected
                )
        
        main_width = pygui.get_item_width("Primary Window") or 1400
        main_height = pygui.get_item_height("Primary Window") or 900
        modal_x = int((main_width / 2 - modal_width / 2))
        modal_y = int((main_height / 2 - modal_height / 2))
        pygui.set_item_pos("change_type_window", [modal_x, modal_y])

    def on_change_type_selected(self, sender, app_data, user_data):
        if not self.ui.state.selected_node:
            ErrorHandler.throw_warning("No node selected")
            return

        old_node = self.ui.state.selected_node
        NewNodeClass = user_data
        current_type_name = type(old_node).__name__
        new_type_name = NewNodeClass.__name__
        
        if new_type_name == current_type_name:
            if pygui.does_item_exist("change_type_window"):
                pygui.delete_item("change_type_window")
            return
        
        try:
            new_node = NewNodeClass()
            for attr, value in vars(old_node).items():
                if attr.startswith("_") or attr in ("runtime_script",):
                    continue
                try:
                    setattr(new_node, attr, value)
                except Exception:
                    pass
            if old_node._parent:
                parent = old_node._parent
                parent._children.remove(old_node)
                parent._children.append(new_node)
                new_node._parent = parent
            
            for child in old_node._children:
                child._parent = new_node
            new_node._children = old_node._children
            old_node._children = []
            
            self.ui.state.selected_node = new_node
            
            self.ui._update_hierarchy()
            
            self.ui.inspector.update(new_node)
            
            ErrorHandler.throw_success(f"Changed node type from {current_type_name} to {new_type_name}")
            
        except Exception as e:
            ErrorHandler.throw_error(f"Failed to change node type: {e}")
        
        if pygui.does_item_exist("change_type_window"):
            pygui.delete_item("change_type_window")
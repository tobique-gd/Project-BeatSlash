from . import ErrorHandler

#scenes store a collection of nodes
class Scene:
    def __init__(self, name, root, path=None):
        self.name = name
        self.root = root
        self.deletion_queue = []
        self.path = path
    
    def _ready(self):
        self._ready_node(self.root)

    def _ready_node(self, node):
        if hasattr(node, "runtime_script") and node.runtime_script:
            node.runtime_script._ready()

        for child in getattr(node, "_children", []):
            self._ready_node(child)

    def _process(self, delta):
        self._process_node(self.root, delta)
        self._process_deletion_queue()

    def _process_node(self, node, delta):

        if hasattr(node, "runtime_script") and node.runtime_script:
            node.runtime_script._process(delta)

        node._update(delta)
        
        if getattr(node, "_queued_for_deletion", False):
            if node not in self.deletion_queue:
                self.deletion_queue.append(node)

        for child in getattr(node, "_children", []):
            self._process_node(child, delta)
    
    def _process_deletion_queue(self):
        if not self.deletion_queue:
            return False
        
        nodes_deleted = False
        for node in self.deletion_queue:
            if node == self.root:
                continue
            
            parent = getattr(node, "_parent", None)
            if parent:
                try:
                    parent.remove_child(node)
                    nodes_deleted = True
                except Exception as e:
                    ErrorHandler.throw_error(f"Failed to delete node {node.name}: {e}")
        
        self.deletion_queue.clear()
        return nodes_deleted

    def _input(self, _event):
        self._input_node(self.root, _event)
    
    def _input_node(self, node, _event):
        if node.runtime_script:
            node.runtime_script._input(_event)
        
        for child in node._children:
            self._input_node(child, _event)
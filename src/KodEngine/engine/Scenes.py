from . import ErrorHandler
from . import Nodes

#scenes store a collection of nodes
class Scene:
    """Runtime scene container that owns the root node and frame queues."""

    def __init__(self, name, root, path=None):
        """Create a scene.

        Parameters
        ----------
        name:
            Scene name.
        root:
            Root node for the scene graph.
        path:
            Optional source file path.
        """
        self.name = name
        self.root = root
        self.deletion_queue = []
        self.path = path
    
    def _ready(self):
        """Call the root script's ready hook if the scene has one."""
        if self.root is not None and hasattr(self.root, "runtime_script") and self.root.runtime_script:
            self.root.runtime_script._ready()

    def _process(self, delta):
        """Advance the scene simulation by one frame.

        Parameters
        ----------
        delta:
            Frame delta time in seconds.
        """
        self._process_node(self.root, delta)
        self._process_deletion_queue()

    def _process_ui(self, viewport_size):
        """Run UI processing for the root control tree.

        Parameters
        ----------
        viewport_size:
            Current viewport size used by controls.
        """
        if self.root is None or viewport_size is None:
            return

        def traverse(node):
            if isinstance(node, Nodes.Control):
                parent = getattr(node, "_parent", None)
                if not isinstance(parent, Nodes.Control):
                    node.process_ui(viewport_size)
                return

            for child in getattr(node, "_children", []):
                traverse(child)

        traverse(self.root)

    def _process_node(self, node, delta):
        """Process a node, its runtime script, and all descendants."""

        if hasattr(node, "runtime_script") and node.runtime_script:
            node.runtime_script._process(delta)

        node._update(delta)
        
        if getattr(node, "_queued_for_deletion", False):
            if node not in self.deletion_queue:
                self.deletion_queue.append(node)

        for child in getattr(node, "_children", []):
            self._process_node(child, delta)
    
    def _process_deletion_queue(self):
        """Remove nodes queued for deletion and report whether any were removed.

        Returns
        -------
        bool
            ``True`` when at least one node was deleted.
        """
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
        """Forward an input event through the scene tree."""
        self._input_node(self.root, _event)
    
    def _input_node(self, node, _event):
        """Deliver an input event to a node and its descendants."""
        if node.runtime_script:
            node.runtime_script._input(_event)

        if hasattr(node, "_input"):
            node._input(_event)
        
        for child in node._children:
            self._input_node(child, _event)
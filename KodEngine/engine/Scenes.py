class Scene:
    def __init__(self, name, root):
        self.name = name
        self.root = root
    
    def _ready(self):
        self._ready_node(self.root)

    def _ready_node(self, node):
        if hasattr(node, "script") and node.script:
            node.script._ready()

        for child in getattr(node, "_children", []):
            self._ready_node(child)

    def _process(self, delta):
        self._process_node(self.root, delta)

    def _process_node(self, node, delta):

        if hasattr(node, "script") and node.script:
            node.script._process(delta)

        node._update(delta)

        for child in getattr(node, "_children", []):
            self._process_node(child, delta)

    def _input(self, _event):
        self._input_node(self.root, _event)
    
    def _input_node(self, node, _event):
        if node.script:
            node.script._input(_event)
        
        for child in node._children:
            self._input_node(child, _event)
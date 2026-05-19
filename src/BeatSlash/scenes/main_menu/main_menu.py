# Script Template 
        
def _ready(self):
    self.node.get_node("VBoxContainer/ContinueButton").connect("on_pressed", target=self, method="_on_play_pressed")
    self.node.get_node("VBoxContainer/ExitButton").connect("on_pressed", target=self, method="_on_quit_pressed")
    print("Main Menu ready")

def _process(self, delta):
    pass # Called every frame

def _input(self, events):
    pass # Grab inputs from pygame

def _on_play_pressed(self):
    print("changing scene...")
    self.node.change_scene_to("scenes/map_tiles/tile_left_right.kscn")

def _on_quit_pressed(self):
    print("Quitting game...")
    self.node.quit()

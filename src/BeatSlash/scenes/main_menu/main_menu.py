# Script Template 
        
def _ready(self):
    self.node.get_node("VBoxContainer/ContinueButton").connect("on_pressed", target=self, method="_on_play_pressed")
    self.node.get_node("VBoxContainer/ExitButton").connect("on_pressed", target=self, method="_on_quit_pressed")

    self.node.get_node("AudioPlayer").play()

def _process(self, delta):
    pass # Called every frame

def _input(self, events):
    pass # Grab inputs from pygame

def _on_play_pressed(self):
    self.node.change_scene_to("scenes/main_menu/start_screen.kscn")

def _on_quit_pressed(self):
    self.node.quit()

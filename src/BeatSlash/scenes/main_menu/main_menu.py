# Script Template 
        
def _ready(self):
    self.fader = self.node.get_node("Fader")
    self._fade_duration = 2.0
    self._fade_elapsed = 0.0

    if self.fader is not None:
        self.fader.tint = (1.0, 1.0, 1.0, 1.0)

    self.node.get_node("VBoxContainer/ContinueButton").connect("on_pressed", target=self, method="_on_play_pressed")
    self.node.get_node("VBoxContainer/ExitButton").connect("on_pressed", target=self, method="_on_quit_pressed")

    self.node.get_node("AudioPlayer").play()

def _process(self, delta):
    if self.fader is not None and self._fade_elapsed < self._fade_duration:
        self._fade_elapsed = min(self._fade_duration, self._fade_elapsed + delta)
        fade_progress = self._fade_elapsed / self._fade_duration if self._fade_duration > 0 else 1.0
        alpha = max(0.0, 1.0 - fade_progress)
        self.fader.tint = (1.0, 1.0, 1.0, alpha)

def _input(self, events):
    pass # Grab inputs from pygame

def _on_play_pressed(self):
    self.node.change_scene_to("scenes/main_menu/start_screen.kscn")

def _on_quit_pressed(self):
    self.node.quit()

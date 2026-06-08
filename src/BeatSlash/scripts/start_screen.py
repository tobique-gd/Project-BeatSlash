# Script Template 
        
import json
import os

def _ready(self):
    self.play_button = self.node.get_node("PlayButton")
    self.back_button = self.node.get_node("BackButton")
    self.play_button.connect("on_pressed", self.on_play_pressed)
    self.back_button.connect("on_pressed", self.on_back_pressed)
    self._last_credits = None
    
    self.load_upgrades()
    self.refresh_credits_label()

def load_upgrades(self):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    defs_path = os.path.join(current_dir, "..", "data", "upgrades.json")
    save_path = os.path.join(current_dir, "..", "data", "save.json")

    if not os.path.exists(defs_path):
        return

    from KodEngine.engine.ResourceServer import SceneLoader

    with open(defs_path, "r") as f:
        defs_data = json.load(f)
        
    defs = defs_data.get("upgrades", [])

    try:
        with open(save_path, "r") as f:
            save = json.load(f)
    except Exception:
        save = {"player": {"credits": 0}, "upgrades": {}}

    upgrades1 = self.node.get_node("Upgrades1")
    upgrades2 = self.node.get_node("Upgrades2")

    powerup_scene_path = os.path.join(current_dir, "..", "scenes", "powerup_button.kscn")

    for i, upg in enumerate(defs):
        container = upgrades1 if i < 3 else upgrades2
        if not container:
            continue

        scene = SceneLoader.load(powerup_scene_path)
        if scene and scene.root:
            box = scene.root
            container.add_child(box)

            saved_level = int(save.get("upgrades", {}).get(upg.get("id"), int(upg.get("level", 1))))
            cost = int(upg["base_cost"] * (upg["cost_multiplier"] ** (saved_level - 1)))

            if hasattr(box, "runtime_script") and box.runtime_script is not None:
                if hasattr(box.runtime_script, "set_data"):
                    box.runtime_script.set_data(upg.get("id"), upg["name"], upg["description"], cost, saved_level, upg.get("base_cost"), upg.get("cost_multiplier"))
                elif hasattr(box.runtime_script, "_module") and hasattr(box.runtime_script._module, "set_data"):
                    box.runtime_script._call("set_data", upg.get("id"), upg["name"], upg["description"], cost, saved_level, upg.get("base_cost"), upg.get("cost_multiplier"))

def refresh_credits_label(self):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    save_path = os.path.join(current_dir, "..", "data", "save.json")

    try:
        with open(save_path, "r") as f:
            save = json.load(f)
    except Exception:
        save = {"player": {"credits": 0}}

    try:
        credits = int(save.get("player", {}).get("credits", 0))
    except Exception:
        credits = 0

    if self._last_credits == credits:
        return

    credits_label = self.node.get_node("CreditsLabel")
    if credits_label is not None:
        try:
            credits_label.text = str(credits)
        except Exception:
            pass

    self._last_credits = credits

def _process(self, delta):
    self.refresh_credits_label()

def _input(self, events):
    pass # Grab inputs from pygame

def on_play_pressed(self):
    self.node.change_scene_to("scenes/map_tiles/dungeon_root.kscn")

def on_back_pressed(self):
    self.node.change_scene_to("scenes/main_menu/main_menu.kscn")
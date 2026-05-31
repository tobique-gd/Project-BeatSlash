import json
import os


def _ready(self):
    self.name_label = self.node.get_node("NameLabel")
    self.desc_label = self.node.get_node("DescLabel")
    self.cost_label = self.node.get_node("CostLbael")
    self.buy_button = self.node.get_node("BuyButton")
    
    # connect buy button using method name to avoid duplicate bound-method connections
    if self.buy_button and hasattr(self.buy_button, "connect"):
        try:
            self.buy_button.connect("on_pressed", self.on_buy_pressed)
        except Exception:
            pass

    # internal state set via set_data
    self.upgrade_id = None
    self.base_cost = None
    self.cost_multiplier = None
    self.level = None


def set_data(self, upgrade_id, name, description, cost, level, base_cost=None, cost_multiplier=None):
    self.upgrade_id = upgrade_id
    self.base_cost = base_cost
    self.cost_multiplier = cost_multiplier
    self.level = level

    if self.name_label:
        self.name_label.text = f"{name} {level}"
    if self.desc_label:
        self.desc_label.text = description
    if self.cost_label:
        self.cost_label.text = f"Cost: {cost}"


def on_buy_pressed(self):
    # Use a separate save file for player state and purchased levels
    if not self.upgrade_id:
        return

    current_dir = os.path.dirname(os.path.abspath(__file__))
    defs_path = os.path.join(current_dir, "..", "data", "upgrades.json")
    save_path = os.path.join(current_dir, "..", "data", "save.json")

    # load definitions to get base cost / multiplier
    defs = {}
    try:
        with open(defs_path, "r") as f:
            defs = json.load(f)
    except Exception:
        pass

    defs_map = {u.get("id"): u for u in defs.get("upgrades", [])} if defs else {}

    # ensure save exists
    if not os.path.exists(save_path):
        # create a basic save using defaults from defs
        save_data = {"player": {"credits": 0}, "upgrades": {}}
        for uid, u in defs_map.items():
            save_data["upgrades"][uid] = int(u.get("level", 1))
        try:
            with open(save_path, "w") as f:
                json.dump(save_data, f, indent=4)
        except Exception:
            return

    try:
        with open(save_path, "r") as f:
            save = json.load(f)
    except Exception:
        return

    credits = int(save.get("player", {}).get("credits", 0))
    saved_level = int(save.get("upgrades", {}).get(self.upgrade_id, self.level or 1))

    # compute cost using saved_level
    def_entry = defs_map.get(self.upgrade_id, {})
    base = def_entry.get("base_cost", self.base_cost or 0)
    mult = def_entry.get("cost_multiplier", self.cost_multiplier or 1)
    cost = int(base * (mult ** (saved_level - 1)))

    if credits < cost:
        # not enough credits
        return

    # apply purchase
    credits -= cost
    new_level = saved_level + 1
    save.setdefault("upgrades", {})[self.upgrade_id] = new_level
    save.setdefault("player", {})["credits"] = credits

    try:
        with open(save_path, "w") as f:
            json.dump(save, f, indent=4)
    except Exception:
        return

    # update displayed values
    new_cost = int(base * (mult ** (new_level - 1)))
    name = def_entry.get("name", "")
    desc = def_entry.get("description", "")
    self.set_data(self.upgrade_id, name, desc, new_cost, new_level, base, mult)

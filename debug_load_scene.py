import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from KodEngine.engine.ResourceServer import SceneLoader
from KodEngine.engine.ResourceServer import ResourceLoader

# Set project root to current directory
ResourceLoader.set_project_root(os.getcwd())

scene_path = "src/BeatSlash/scenes/world.kscn"
print(f"Loading scene: {scene_path}")

try:
    scene = SceneLoader.load(scene_path)
    if scene:
        print("Scene loaded successfully.")
    else:
        print("Failed to load scene.")
except Exception as e:
    print(f"Error loading scene: {e}")

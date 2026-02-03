import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True)
    args = parser.parse_args()

    runtime_file = os.path.abspath(__file__)
    src_root = os.path.dirname(os.path.dirname(os.path.dirname(runtime_file)))
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from KodEngine.engine import Kod, ResourceManager

    scene_path = args.scene
    if not os.path.isabs(scene_path):
        scene_path = os.path.abspath(scene_path)

    try:
        settings = Kod.Settings()
        app = Kod.App(settings, editor_mode=False)
        scene = ResourceManager.SceneLoader.load(scene_path)
        if scene:
            app.set_scene(scene)
            app.run()
        else:
            print(f"ERROR: Failed to load scene: {scene_path}")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

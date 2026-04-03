# Engine Runtime Reference

## Runtime Entry

Runtime starts in Kod.App inside src/KodEngine/engine/Kod.py. The app creates display surfaces, owns timing state, and runs the main loop.

## Core Configuration

Kod.Settings stores project configuration shared by runtime and editor mode. Runtime uses project directory, output resolution, internal resolution, physics substeps, main scene path, and target FPS.

## Frame Lifecycle

App.run() validates screen and scene, resets internal surfaces, and calls scene _ready once before the loop starts. Each frame then polls events, forwards input to the scene, executes scene _process(delta), partitions nodes into rendering and physics buckets, resolves the camera, advances physics, renders the frame, presents the internal surface, and swaps buffers.

## Scene Loop Contract

Scene in src/KodEngine/engine/Scenes.py owns the root node and a deferred deletion queue. _ready walks the tree and calls runtime script _ready handlers. _process walks the tree every frame, calls runtime script _process, and executes deferred deletion. _input forwards every event to runtime script _input handlers.

## Rendering Pipeline

Renderer2D in src/KodEngine/engine/RenderingServer.py utilizes a custom pipeline with pygame as the rasterizer. Each frame starts with getting an allocated list of Renderable Nodes which the renderer sorts by z-index, then sorts each YSort node separately and then dispatches the rendering implementation for the respective the nodes. The renderer tries to be as permormant as possible utilizing frustum culling for all nodes and chunking systems in tilemaps.

## Physics Pipeline

PhysicsSolver2D in src/KodEngine/engine/PhysicsServer.py performs rectangle collision resolution in substeps. It checks DynamicBody2D and KinematicBody2D against rectangle collision shapes. Resolution is axis separated. Dynamic bodies integrate velocity during the step. Colliding velocity components are zeroed when velocity exists. It is built using a standard separation axis theorem algorithm and loops through all bodies. No spatial partitioning is implemented for now.

## Camera Resolution

Runtime camera resolution first uses the camera set explicitly on App. If no explicit camera is set, runtime searches the scene for the first Camera2D with current equal to True. If none is found, runtime falls back to an internal Camera2D instance.

## Runtime in Editor Play Mode

Editor play mode starts src/KodEngine/editor/subprocess/runtime.py in a separate process. The subprocess accepts a scene path and optional JSON settings overrides, sets project root resolution, loads the scene through SceneLoader, and runs a standard Kod.App runtime loop.

# KodEngine Architecture Map

This document explains how KodEngine operates at a high level, and how the editor layers on top of the same core runtime.

## 1. System Overview

KodEngine has two operating modes:

1. Runtime game mode
2. Editor mode

Both modes share the same core engine modules for scene graph, resources, serialization, and rendering.

Core entry points:

- Runtime app bootstrap: [src/KodEngine/engine/Kod.py](../src/KodEngine/engine/Kod.py)
- Editor bootstrap: [src/KodEngine/editor/Editor.py](../src/KodEngine/editor/Editor.py)
- Runtime subprocess for Play Scene: [src/KodEngine/editor/subprocess/runtime.py](../src/KodEngine/editor/subprocess/runtime.py)

## 2. Runtime Engine Map

High-level structure:

Settings -> App -> SceneLoader -> Scene/Nodes -> Main Loop -> Renderer -> Display

Detailed structure:

1. Settings are created in [src/KodEngine/engine/Kod.py](../src/KodEngine/engine/Kod.py).
2. App initializes pygame surfaces, renderer, clock, and camera fallback.
3. Scene is loaded through [src/KodEngine/engine/ResourceServer.py](../src/KodEngine/engine/ResourceServer.py).
4. Scene graph contains Node objects from [src/KodEngine/engine/Nodes.py](../src/KodEngine/engine/Nodes.py).
5. Main loop handles events, input dispatch, process update, camera resolution, and frame render.
6. Renderer in [src/KodEngine/engine/RenderingServer.py](../src/KodEngine/engine/RenderingServer.py) draws scene.

Runtime loop responsibilities:

- Input dispatch: Scene._input(event)
- Update dispatch: Scene._process(delta)
- Camera: App.resolve_camera()
- Draw: Renderer.render_frame(scene, camera)

## 3. Scene Graph and Data Ownership

The scene graph is hierarchical and data-oriented:

1. Node owns transform and common fields
2. Specialized nodes add behavior or resources
3. save_data and load_data are special methods each node has that define how each node should be serialized for saving and loading

## 4. Resource and Serialization Pipeline

Resource system pipeline:

1. ResourceLoader resolves absolute path and caches instances
2. SceneLoader serializes node trees to JSON
3. SceneLoader deserializes JSON back to node instances
4. Nested resources are encoded with marker payloads

Key components:

- ResourceLoader and SceneLoader: [src/KodEngine/engine/ResourceServer.py](../src/KodEngine/engine/ResourceServer.py)
- Resource base and concrete classes: [src/KodEngine/engine/Resources.py](../src/KodEngine/engine/Resources.py)

Current scene formatting note:

- Scenes are saved as .kscn files which are just human readable JSON files under the hood

## 5. Rendering Pipeline

Renderer architecture:

1. Build drawable node structure
2. Render world nodes to internal surface
3. Apply camera transform and zoom
4. Scale to viewport output surface

Files:

- Main renderer: [src/KodEngine/engine/RenderingServer.py](../src/KodEngine/engine/RenderingServer.py)
- Optional debug draw command server: [src/KodEngine/editor/DebugRenderingServer.py](../src/KodEngine/editor/DebugRenderingServer.py)

## 6. Editor Architecture Map

Editor uses DearPyGui for tooling UI and a hidden pygame surface for world rendering.

High-level flow:

Editor boot -> Load scene -> UI + viewport update loop -> gizmo/input tools -> save/run commands

Main editor pieces:

- Editor: [src/KodEngine/editor/Editor.py](../src/KodEngine/editor/Editor.py)
- UI composition: [src/KodEngine/editor/EditorUI.py](../src/KodEngine/editor/EditorUI.py)
- Inspector logic: [src/KodEngine/editor/ui_components/InspectorPanel.py](../src/KodEngine/editor/ui_components/InspectorPanel.py)
- File tree: [src/KodEngine/editor/ui_components/FileSystem.py](../src/KodEngine/editor/ui_components/FileSystem.py)
- Gizmo and viewport interaction: [src/KodEngine/editor/EditorGizmo.py](../src/KodEngine/editor/EditorGizmo.py)
- Overlay rendering hooks: [src/KodEngine/editor/EditorOverlay.py](../src/KodEngine/editor/EditorOverlay.py)
- Debug draw backend: [src/KodEngine/editor/DebugRenderingServer.py](../src/KodEngine/editor/DebugRenderingServer.py)

Editor frame lifecycle:

1. Drain queued editor commands
2. Process gizmo and viewport interactions
3. Update nodes with editor_update
4. Queue overlay debug primitives
5. Render scene to internal surface
6. Push frame into DearPyGui viewport texture

## 8. Play In Editor Process Model

When Run Scene is triggered in editor:

1. Current scene is saved to disk
2. Editor starts subprocess runtime module
3. Subprocess creates a runtime App in non-editor mode
4. Scene is loaded and run with normal game loop

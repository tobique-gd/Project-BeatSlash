# Editor Reference

## Editor Entry and Mode

Editor bootstraps from KodEditor in src/KodEngine/editor/Editor.py. DearPyGui handles tool UI. A hidden pygame surface renders the scene. Editor mode reuses runtime scene, node, and resource systems.

## Editor Session Structure

EditorSessionState in src/KodEngine/editor/EditorModels.py stores current selection, copied node data, hierarchy selectable mapping, and per-tilemap paint selections. EditorCommand and EditorCommandType define command routing.

## Editor Frame Responsibilities

Each frame drains queued commands, processes gizmo and tool interaction, and traverses nodes with editor_update. The editor then queues overlays, renders through Renderer2D, and uploads RGBA data to the viewport texture.

## Core Editor Modules

Core interaction modules are EditorGizmoController, EditorViewportToolController with TileMapPaintTool, and EditorOverlayRenderer. EditorUI composes MenuBar, HierarchyPanel, InspectorPanel, ViewportPanel, ConsolePanel, FileSystem, and Dialogs.

## Panel Responsibilities

Hierarchy renders scene structure, selection state, and drag-and-drop reparenting with cycle protection. Inspector edits reflected fields, writable properties, resource slots, and type-specific values. Viewport displays runtime output and manages texture resize and frame upload. FileSystem handles browsing, open actions, file moves, and creation dialogs. MenuBar exposes save, run, and editor settings commands.

## Selection and Transform Workflow

Node selection is computed through world-space bounds tests against Node2D instances. The translate gizmo supports X, Y, and XY constraints. Dragging applies world-space transforms with camera zoom compensation.

## Runtime and Editor Separation

Edit mode and play mode are process separated. Edit mode renders in-process for tooling feedback. Play mode runs selected scenes in a subprocess runtime. This separation preserves editor responsiveness and isolates runtime state.

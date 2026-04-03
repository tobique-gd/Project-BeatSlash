# Introduction

KodEngine is a lightweight 2D game engine built on pygame with an integrated visual editor. It is features a very similar workflow to other engines featuring 2D such as Godot or Unity.

KodEngine is useful when you want the control and simplicity of pygame but need better structure as a project grows. You can build gameplay with script-driven nodes, save scenes as data, and iterate in an editor without writing custom tooling for every project.

## How It Works

Runtime mode executes a standard game loop with scene update, physics step, and rendering pass. Scenes are node trees. Nodes own transform and behavior data. Resources handle textures, audio, scripts, animations, and tilesets. Scene files are stored as readable .kscn JSON.

Editor mode uses the same runtime systems for viewport rendering and scene data, so behavior in editor and play mode stays consistent. The editor adds hierarchy management, inspector editing, tile painting, gizmos, and run-in-subprocess play testing.

## Why Use It

You shouldn't.

## Suggested Reading Order

Start with Engine Runtime Reference to understand execution flow. Continue with Engine Nodes and Resources Reference to understand data and serialization. Read Editor Reference for tooling behavior. Use Node Class Reference as API lookup during implementation.

## Scope

The reference targets the implementation in src/KodEngine. It reflects the current code in engine and editor modules.

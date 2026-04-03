# TileMap2D

TileMap2D stores layered tile grids and chunked render data.

| Function | Description |
| --- | --- |
| __init__() | Initializes tileset slot, bounds, layers, and chunk cache. |
| _on_enter() | Rebuilds chunked tile data when entering scene tree. |
| chunk_size (property getter) | Returns chunk dimension in tiles. |
| chunk_size (property setter) | Sets chunk dimension and rebuilds chunk cache. |
| preprocess_tile_data() | Converts tile layers into chunked runtime data. |
| shrink_to_fit(fill_value=-1) | Reduces bounds to non-empty tile extents. |
| _normalize_bounds(bounds) | Normalizes min and max tile bounds ordering. |
| _grid_dimensions(bounds) | Computes grid width and height from bounds. |
| _empty_grid(bounds=None, fill_value=-1) | Creates an empty tile grid for bounds. |
| _normalize_tile_data(value, bounds=None, fill_value=-1) | Normalizes raw tile array into bounded int grid. |
| _normalize_layer_index(layer) | Coerces layer id to int. |
| _normalize_tile_layers(value, bounds=None, fill_value=-1) | Normalizes tile layer dictionary input. |
| tileset (property getter) | Returns tileset resource. |
| bounds (property getter) | Returns tile bounds. |
| bounds (property setter) | Updates bounds while preserving existing data. |
| tile_layers (property getter) | Returns tile layer map. |
| tile_layers (property setter) | Assigns normalized tile layers and shrinks bounds. |
| tileset (property setter) | Assigns tileset resource from object or path. |
| set_bounds(bounds, preserve=True, fill_value=-1) | Resizes map bounds and remaps layer content. |
| ensure_layer(layer, fill_value=-1) | Ensures a target layer exists and returns it. |
| get_tile_id(tile_pos, layer=0) | Reads tile id at tile coordinates and layer. |
| set_tile_id(tile_pos, tile_id, layer=0) | Writes tile id, expands bounds when needed, and rebuilds cache. |
| get_layer_indices() | Returns sorted layer indices. |
| save_data() | Serializes bounds, layers, and tileset reference. |
| load_data(data) | Deserializes bounds, layers, and tileset reference. |
| tile_to_world(tile_pos) | Converts tile coordinates to local world coordinates. |
| world_to_tile(world_pos) | Converts local world coordinates to tile coordinates. |
| world_bounds (property getter) | Returns world-space bounds for current tile bounds. |

| Property | Description |
| --- | --- |
| position | Local tilemap position inherited from Node2D. |
| rotation | Local rotation inherited from Node2D. |
| z_index | Render ordering inherited from Node2D. |
| chunk_size | Tile chunk size used when building cached render data. |
| tileset | Bound tileset resource or resource path. |
| bounds | Inclusive tile coordinate bounds for the map. |
| tile_layers | Layered tile grid data keyed by layer index. |
| world_bounds | World-space bounds derived from the current tile bounds. |

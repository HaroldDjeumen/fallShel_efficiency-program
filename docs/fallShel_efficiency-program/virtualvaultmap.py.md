# virtualvaultmap.py 🗺️

This module generates a vault layout from JSON data. It builds a grid map, places rooms, prints an ASCII/colored view in terminal, and renders graphical images. It suits tools that visualize structured vault configurations.

## Purpose

- Load vault room definitions from a JSON file.
- Arrange rooms on a fixed grid.
- Display the map in terminal with ANSI colors.
- Export plain text and PNG representations.

## Dependencies

The script relies on standard libraries and Pillow for image rendering:

- **json**, **os**, **random**  
- **PIL**: `Image`, `ImageDraw`, `ImageFont` 

## Function Summary

| Function                        | Description                                                  |
|---------------------------------|--------------------------------------------------------------|
| `run(json_path)`                | Entry point: load JSON, build vault, invoke outputs.        |
| `get_room_width(type, level)`   | Compute horizontal span of a room on the grid.              |
| `place_room(...)`               | Populate the grid cells with room identifiers.              |
| `print_vault_map_terminal(v)`   | Print a color‐coded vault layout in the terminal.           |
| `print_vault_map(v)`            | Output the map in plain text and save to `vault_map.txt`.   |
| `draw_vault(v, filename, legendfile)` | Render the vault as PNG images with a legend.    |

## Main Entry Point

### run(json_path)

This function orchestrates the entire process:

```python
def run(json_path):
    """
    Load vault JSON, place rooms, and generate all outputs.
    """
    # 1. Initialize empty grid (25×26)
    # 2. Read JSON from Downloads/<json_path>
    # 3. Place each room via place_room
    # 4. Print and save textual map
    # 5. Draw and save graphical map
```

## Room Layout Helpers

### get_room_width

Compute how many columns a room occupies:

```python
def get_room_width(room_type, merge_level):
    if room_type == "Elevator":
        return 1
    return 3 * merge_level
```

- **Elevator** rooms always occupy 1 column.  
- Other rooms span `3 × merge_level` columns.

### place_room

Populate the `vault` grid for a single room:

```python
def place_room(vault, room_type, row, col, merge_level, room_level):
    width = get_room_width(room_type, merge_level)
    # Clamp to grid bounds
    start = max(0, col)
    end = min(COLUMNS, col + width)
    # Fill cells with metadata string
    for c in range(start, end):
        vault[row][c] = (
            f"{room_type} at level= {room_level}"
            f" (MergeLevel: {merge_level})"
        )
```

- Ignores rooms outside row bounds.  
- Ensures placement fits within columns.

## Terminal Output

### print_vault_map_terminal

Print a styled map with colors and a legend:

```python
def print_vault_map_terminal(vault):
    """
    Display each floor row, grouping consecutive cells.
    Use ANSI color codes to differentiate room types.
    """
```

- Skips empty rows for brevity.  
- Groups identical adjacent cells.  
- Builds a legend correlating colors to room types.

### print_vault_map

Produce original‐format text and save to `vault_map.txt`:

```python
def print_vault_map(vault):
    for row in vault:
        print(" | ".join(cell or "Empty" for cell in row))
    # Also writes the same to vault_map.txt
```

- Calls `print_vault_map_terminal` for console view.

## Graphical Output 🖼️

### draw_vault

Render the vault and its legend as PNG images:

```python
def draw_vault(vault, filename="vault.png", legendfile="legend.png"):
    """
    - Assign a random hex color per unique room.
    - Draw grid squares using Pillow.
    - Compose legend alongside the map.
    """
```

- Uses constants `CELL = 40`, `CELL_H = 60` for cell size.  
- Attempts to load `arial.ttf`, defaults on failure.  
- Saves two files: `vault.png` (map) and `legend.png` (legend).

## Usage Example

```python
from virtualvaultmap import run

# Assuming JSON file in Downloads named 'vault_config.json'
run("vault_config.json")
```

This call produces:

- A colored terminal map  
- A plain-text file `vault_map.txt`  
- Image files `vault.png` and `legend.png`  

```card
{
  "title": "Note",
  "content": "Place your JSON in the Downloads folder before running."
}
```

## Integration

This module plugs into GUI utilities such as **fallout_gui.py** to visualize vault layouts within a desktop application. It stands alone but exports powerful output for other components.

## Potential Improvements 🛠️

- Parameterize grid size instead of fixed constants.  
- Allow custom color palettes or themes.  
- Add robust error handling for missing or malformed JSON.  
- Support dynamic export formats (SVG, PDF).

---

*Generated based on the provided code and dependency mapping.*
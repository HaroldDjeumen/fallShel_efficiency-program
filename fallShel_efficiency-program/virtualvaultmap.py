import json
import os
import random

def run(json_path):
    ROWS = 25  #floors
    COLUMNS = 26  #width
    vault = [[None for _ in range(COLUMNS)] for _ in range(ROWS)]

    downloads_folder = os.path.expanduser(r"~\Downloads")
    file_path = os.path.join(downloads_folder, json_path)

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    vault_file = "vault_map.txt"

    rooms = data["vault"]["rooms"]

    for room in rooms:
        Roomtype = room.get("type")
        Row = room.get("row")
        Column = room.get("col")
        MergeLevel = room.get("mergeLevel")
        Roomlevel = room.get("level")

        def get_room_width( Roomtype,MergeLevel):
            if Roomtype == "Elevator":
                return 1

            return 3 * MergeLevel

        def place_room(vault, Roomtype, Row, Column, MergeLevel, RoomLevel):
            width = get_room_width(Roomtype, MergeLevel)
            if Row < 0 or Row >= ROWS:
                return  # or log and continue
            start = max(0, Column)
            end = min(COLUMNS, Column + width)
            if start >= end:
                print("\n")
                return  # nothing fits
            for c in range(start, end):
                vault[Row][c] = Roomtype + " at level= " + str(RoomLevel)+ f" (MergeLevel: {MergeLevel})"

        place_room(vault, Roomtype, Row, Column, MergeLevel, Roomlevel)
    
    def print_vault_map_terminal(vault):
        """Print a nicely formatted vault map to terminal"""
        print("\n" + "="*80)
        print("VAULT MAP")
        print("="*80)
        
        # Get unique room types for color coding
        room_types = {}
        for row in vault:
            for cell in row:
                if cell is not None and "Empty" not in cell:
                    # Extract room type (before " at level=")
                    room_type = cell.split(" at level=")[0]
                    if room_type not in room_types:
                        room_types[room_type] = len(room_types)
        
        # ANSI color codes for terminal
        colors = [
            '\033[91m',  # Red
            '\033[92m',  # Green
            '\033[93m',  # Yellow
            '\033[94m',  # Blue
            '\033[95m',  # Magenta
            '\033[96m',  # Cyan
            '\033[97m',  # White
        ]
        reset = '\033[0m'
        
        # Print each row
        for row_idx, row in enumerate(vault):
            # Skip completely empty rows for cleaner display
            if all(cell is None for cell in row):
                continue
            
            print(f"\nFloor {row_idx:2d}: ", end="")
            
            # Group consecutive same rooms
            i = 0
            while i < len(row):
                cell = row[i]
                
                if cell is None:
                    print("[ Empty ]", end=" ")
                    i += 1
                else:
                    # Extract room info
                    room_type = cell.split(" at level=")[0]
                    level = cell.split("level= ")[1].split(" ")[0]
                    merge = cell.split("MergeLevel: ")[1].rstrip(")")
                    
                    # Count consecutive cells with same room
                    count = 1
                    while i + count < len(row) and row[i + count] == cell:
                        count += 1
                    
                    # Color code by room type
                    color_idx = room_types.get(room_type, 0) % len(colors)
                    color = colors[color_idx]
                    
                    # Format: [RoomType Lv.X M:Y]
                    room_display = f"{color}[{room_type[:8]:8s} Lv.{level} M:{merge}]{reset}"
                    print(room_display, end=" ")
                    
                    i += count
            
        print("\n\n" + "-"*80)
        print("LEGEND:")
        print("-"*80)
        for room_type, idx in sorted(room_types.items(), key=lambda x: x[1]):
            color = colors[idx % len(colors)]
            print(f"{color}█{reset} {room_type}")
        print("="*80 + "\n")

    def print_vault_map(vault):
        """Original format for txt file"""
        for row in vault:
            print(" | ".join([cell if cell is not None else "Empty" for cell in row]) + "\n")

    # Print nicely to terminal
    print_vault_map_terminal(vault)

    # Save in original format to txt file
    with open(vault_file, "w", encoding="utf-8") as f:
        for row in vault:
            f.write(" | ".join([cell if cell is not None else "Empty" for cell in row]) + "\n")
        print(f"✓ Vault map saved to {vault_file}")


    from PIL import Image, ImageDraw, ImageFont

    CELL = 40
    CELL_H = 60  # height of each grid square

    def draw_vault(vault, filename="vault.png", legendfile="legend.png"):
        ROWS = len(vault)
        COLUMNS = len(vault[0])

        # Compute unique rooms and colors first (so they are available for legend sizing)
        unique_rooms = set(room.lower() for row in vault for room in row if room is not None)
        room_colors = {room: f'#{random.randint(0, 0xFFFFFF):06x}' for room in unique_rooms}

        LEGEND_HEIGHT = 2 * max(1, len(unique_rooms))
        img_height = ROWS * CELL_H + 212
        img = Image.new("RGB", (COLUMNS * CELL,LEGEND_HEIGHT + img_height + 40), "white")
        draw = ImageDraw.Draw(img)
        legend_img = Image.new("RGB",(COLUMNS * CELL,600), "white")
        legend_draw = ImageDraw.Draw(legend_img)


        # choose a font
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except OSError:
            font = ImageFont.load_default()

        for r in range(ROWS):
            for c in range(COLUMNS):
                x1 = c * CELL
                y1 = r * CELL_H
                x2 = x1 + CELL
                y2 = y1 + CELL_H

                room = vault[r][c]
                if room is None:
                    color = "white"
                else:
                    color = room_colors.get(room.lower(), "green")
             
                draw.rectangle([x1, y1, x2, y2], fill=color, outline="black")


        legend_top = ROWS * CELL_H + 20
        left_margin = 3

        x = left_margin
        y = legend_top
        y2 = 20

        for room, color in room_colors.items():

           # Move to next column if this one is full
          if x + 100 > COLUMNS * CELL:
            x = left_margin
            y += 25
            y2 += 25

          # Draw color box
          draw.rectangle(
            [x, y, x + 15, y + 15],
            fill=color,
            outline="black"
          )
          legend_draw.rectangle(
            [x, y2, x + 15, y2 + 15],
            fill=color,
            outline="black"
          )

          # Draw text
          draw.text(
            (x + 25, y),
            room.capitalize(),
            fill = "black",
            font = font
          )
          legend_draw.text(
            (x + 25, y2),
            room.capitalize(),
            fill = "black",
            font = font
          )

          x += 350  

        img.save(filename)
        legend_img.save(legendfile)


    draw_vault(vault)

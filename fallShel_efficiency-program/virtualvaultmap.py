import json
import os
import random


def print_section(title, char="="):
    """Print a formatted section header"""
    width = 100
    print(f"\n{char * width}")
    print(f"{title.center(width)}")
    print(f"{char * width}\n")


def run(json_path):
    ROWS = 25  # floors
    COLUMNS = 26  # width
    vault = [[None for _ in range(COLUMNS)] for _ in range(ROWS)]

    downloads_folder = os.path.expanduser(r"~\Downloads")
    file_path = os.path.join(downloads_folder, json_path)

    print_section("VAULT MAP GENERATOR")
    print(f"Loading vault data from: {file_path}")

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    vault_file = "vault_map.txt"
    rooms = data["vault"]["rooms"]

    print(f"✓ Loaded {len(rooms)} rooms")
    print(f"✓ Vault dimensions: {ROWS} floors × {COLUMNS} width\n")

    def get_room_width(Roomtype, MergeLevel):
        if Roomtype == "Elevator":
            return 1
        return 3 * MergeLevel

    def place_room(vault, Roomtype, Row, Column, MergeLevel, RoomLevel):
        width = get_room_width(Roomtype, MergeLevel)
        if Row < 0 or Row >= ROWS:
            return
        start = max(0, Column)
        end = min(COLUMNS, Column + width)
        if start >= end:
            return
        for c in range(start, end):
            vault[Row][c] = {
                'type': Roomtype,
                'level': RoomLevel,
                'merge': MergeLevel
            }

    # Place all rooms
    print_section("PLACING ROOMS", "-")
    room_count = {}
    for room in rooms:
        Roomtype = room.get("type")
        Row = room.get("row")
        Column = room.get("col")
        MergeLevel = room.get("mergeLevel")
        Roomlevel = room.get("level")

        place_room(vault, Roomtype, Row, Column, MergeLevel, Roomlevel)
        
        # Track room types
        room_count[Roomtype] = room_count.get(Roomtype, 0) + 1

    print("Room Summary:")
    for room_type, count in sorted(room_count.items()):
        print(f"  {room_type}: {count}")

    def print_vault_map(vault):
        """Print vault map in a compact, readable format"""
        print_section("VAULT LAYOUT")
        
        # Create abbreviated room codes for compact display
        room_codes = {}
        for row in vault:
            for cell in row:
                if cell is not None:
                    room_type = cell['type']
                    if room_type not in room_codes:
                        # Create 3-letter code
                        if room_type == "Elevator":
                            room_codes[room_type] = "ELV"
                        else:
                            # Take first 3 letters, uppercase
                            room_codes[room_type] = room_type[:3].upper()
        
        # Print legend
        print("Room Legend:")
        for room_type, code in sorted(room_codes.items()):
            print(f"  [{code}] = {room_type}")
        print()
        
        # Print vault with floor numbers
        print("     " + "".join([f"{i:3}" for i in range(COLUMNS)]))  # Column headers
        print("    " + "┌" + "───" * COLUMNS + "┐")
        
        for floor_idx, row in enumerate(vault):
            row_display = []
            for cell in row:
                if cell is None:
                    row_display.append("   ")
                else:
                    code = room_codes[cell['type']]
                    row_display.append(f"{code}")
            
            # Print floor number and row
            print(f"{floor_idx:2}  │{''.join(row_display)}│")
        
        print("    └" + "───" * COLUMNS + "┘")

    def print_detailed_vault_map(vault):
        """Print detailed vault map with room levels"""
        print_section("DETAILED VAULT MAP")
        
        empty_count = 0
        occupied_count = 0
        
        for floor_idx, row in enumerate(vault):
            print(f"\nFloor {floor_idx + 1:2}:")
            print("─" * 100)
            
            floor_has_rooms = False
            for col_idx, cell in enumerate(row):
                if cell is not None:
                    floor_has_rooms = True
                    size_names = {1: "Small", 2: "Medium", 3: "Large"}
                    size = size_names.get(cell['merge'], "Unknown")
                    print(f"  Col {col_idx:2}: {cell['type']:20} (Level {cell['level']}, {size})")
                    occupied_count += 1
                else:
                    empty_count += 1
            
            if not floor_has_rooms:
                print("  (Empty)")
        
        print(f"\n{'─' * 100}")
        print(f"Total cells: {ROWS * COLUMNS} | Occupied: {occupied_count} | Empty: {empty_count}")

    # Display both map versions
    print_vault_map(vault)
    print_detailed_vault_map(vault)

    # Save to file
    print_section("SAVING FILES", "-")
    
    with open(vault_file, "w", encoding="utf-8") as f:
        f.write("VAULT MAP - TEXT VERSION\n")
        f.write("=" * 100 + "\n\n")
        
        for floor_idx, row in enumerate(vault):
            f.write(f"Floor {floor_idx + 1:2}: ")
            row_text = []
            for cell in row:
                if cell is None:
                    row_text.append("Empty")
                else:
                    row_text.append(f"{cell['type']} (Lvl {cell['level']}, Merge {cell['merge']})")
            f.write(" | ".join(row_text) + "\n")
    
    print(f"✓ Text map saved to: {vault_file}")

    # Generate visual map
    try:
        from PIL import Image, ImageDraw, ImageFont

        CELL = 40
        CELL_H = 60

        def draw_vault(vault, filename="vault.png", legendfile="legend.png"):
            ROWS = len(vault)
            COLUMNS = len(vault[0])

            # Get unique room types
            unique_rooms = set()
            for row in vault:
                for cell in row:
                    if cell is not None:
                        unique_rooms.add(cell['type'].lower())

            # Generate colors
            room_colors = {
                room: f'#{random.randint(0x404040, 0xFFFFFF):06x}' 
                for room in unique_rooms
            }

            LEGEND_HEIGHT = 30 * max(1, len(unique_rooms))
            img_height = ROWS * CELL_H + 250
            img = Image.new("RGB", (COLUMNS * CELL, img_height), "white")
            draw = ImageDraw.Draw(img)
            
            legend_img = Image.new("RGB", (COLUMNS * CELL, 600), "white")
            legend_draw = ImageDraw.Draw(legend_img)

            # Load font
            try:
                font = ImageFont.truetype("arial.ttf", 16)
                small_font = ImageFont.truetype("arial.ttf", 10)
            except OSError:
                font = ImageFont.load_default()
                small_font = ImageFont.load_default()

            # Draw vault
            for r in range(ROWS):
                for c in range(COLUMNS):
                    x1 = c * CELL
                    y1 = r * CELL_H
                    x2 = x1 + CELL
                    y2 = y1 + CELL_H

                    cell = vault[r][c]
                    if cell is None:
                        color = "white"
                    else:
                        color = room_colors.get(cell['type'].lower(), "green")

                    draw.rectangle([x1, y1, x2, y2], fill=color, outline="black")
                    
                    # Add level indicator
                    if cell is not None:
                        draw.text(
                            (x1 + 2, y1 + 2),
                            f"L{cell['level']}",
                            fill="black",
                            font=small_font
                        )

            # Draw legend
            legend_top = ROWS * CELL_H + 20
            left_margin = 10
            x = left_margin
            y = legend_top
            y2 = 20

            for room, color in sorted(room_colors.items()):
                if x + 200 > COLUMNS * CELL:
                    x = left_margin
                    y += 30
                    y2 += 30

                # Main image legend
                draw.rectangle([x, y, x + 20, y + 20], fill=color, outline="black")
                draw.text((x + 30, y), room.capitalize(), fill="black", font=font)

                # Separate legend image
                legend_draw.rectangle([x, y2, x + 20, y2 + 20], fill=color, outline="black")
                legend_draw.text((x + 30, y2), room.capitalize(), fill="black", font=font)

                x += 220

            img.save(filename)
            legend_img.save(legendfile)

        draw_vault(vault)
        print(f"✓ Visual map saved to: vault.png")
        print(f"✓ Legend saved to: legend.png")

    except ImportError:
        print("⚠ PIL (Pillow) not installed - skipping image generation")
        print("  Install with: pip install Pillow")

    print_section("VAULT MAP GENERATION COMPLETE")

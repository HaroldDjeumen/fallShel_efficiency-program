import json
import os
import random

ROWS = 25  #floors
COLUMNS = 26  #width
vault = [[None for _ in range(COLUMNS)] for _ in range(ROWS)]

downloads_folder = os.path.expanduser(r"~\Downloads")
file_path = os.path.join(downloads_folder, "Vault1.json")

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
    
    def print_vault_map(vault):
        for row in vault:
            print(" | ".join([cell if cell is not None else "Empty" for cell in row]) + "\n")

print_vault_map(vault)


with open(vault_file, "w", encoding="utf-8") as f:
    for row in vault:
        f.write(" | ".join([cell if cell is not None else "Empty" for cell in row]) + "\n")
    print(f"Vault map saved to {vault_file}")


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

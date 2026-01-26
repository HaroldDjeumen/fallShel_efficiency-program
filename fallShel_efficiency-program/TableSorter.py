import subprocess
import time
import os
import json
import sqlite3
from typing import Collection
import pyodbc


def print_section(title, char="="):
    """Print a formatted section header"""
    width = 80
    print(f"\n{char * width}")
    print(f"{title.center(width)}")
    print(f"{char * width}\n")


def print_subsection(title):
    """Print a formatted subsection header"""
    print(f"\n{'-' * 80}")
    print(f"  {title}")
    print(f"{'-' * 80}")


def run(json_path):
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()

    wCounter = 0
    oCounter = 0 
    jCounter = 0

    SPECIAL = ["Luck", "Strength", "Perception", "Endurance", "Chrisma", "Intelligence", "Agility"]
    delcount = 0
    dwellercount = 0

    downloads_folder = os.path.expanduser(r"~\Downloads")
    file_path = os.path.join(downloads_folder, json_path) 

    print_section("VAULT DATA PROCESSOR")
    print(f"Loading vault data from: {file_path}")

    # Open and read the JSON file
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    dwellers_list = data["dwellers"]["dwellers"]
    rooms = data["vault"]["rooms"]
    storItems = data["vault"]["inventory"]["items"]
    outfit_list = []
    weapon_list = []
    junk_list = []

    print(f"✓ Loaded {len(dwellers_list)} dwellers, {len(rooms)} rooms, {len(storItems)} storage items")

    # Clean up deleted dwellers
    print_subsection("Database Cleanup")
    json_ids = {d["serializeId"] for d in dwellers_list}
    cursor.execute("SELECT dweller_id FROM dwellers")
    db_ids = {row[0] for row in cursor.fetchall()}
    ids_to_delete = db_ids - json_ids
    
    for bad_id in ids_to_delete:
        cursor.execute("DELETE FROM Stats WHERE dweller_id = ?", (bad_id,))
        cursor.execute("DELETE FROM dwellers WHERE dweller_id = ?", (bad_id,))
        delcount += 1
    conn.commit()
    
    if delcount > 0:
        print(f"✓ Removed {delcount} deleted dweller(s) from database")
    else:
        print("✓ No cleanup needed - all dwellers current")

    # Clear working tables
    tables = ["Stats", "TrainingRoom", "CraftingRoom", "ConsumableRoom", "Non_ProductionRoom", "ProductionRoom"]
    for t in tables:
        cursor.execute(f"DELETE FROM {t}")
    conn.commit()
    print(f"✓ Cleared {len(tables)} working tables")

    table_map = {
        "Production": "ProductionRoom",
        "Consumable": "ConsumableRoom",
        "Crafting": "CraftingRoom",
        "Training": "TrainingRoom"
    }

    # Process dwellers
    print_section("PROCESSING DWELLERS")
    
    for idx, d in enumerate(dwellers_list, 1):
        fullname = d.get("name", "") + " " + d.get("lastName", "")
        serialize_id = d.get("serializeId")
        outfit = d.get("equipedOutfit", {})
        outfitId = outfit.get("id")
        h = d.get("health", {})
        health = h.get("healthValue")
        maxhealth = h.get("maxHealth")
        exp = d.get("experience", {})
        lvl = exp.get("currentLevel")
        stats_container = d.get("stats", {})
        weapon = d.get("equipedWeapon", {})

        print(f"\n[{idx}/{len(dwellers_list)}] {fullname}")
        print(f"  ID: {serialize_id}")
        print(f"  Health: {health}/{maxhealth} | Level: {lvl} | Outfit: {outfitId}")

        # Process SPECIAL stats
        stat_list = stats_container["stats"]
        special_display = []
        for i, special_name in enumerate(SPECIAL):
            stats_value = stat_list[i]["value"]
            mods_value = stat_list[i]["mod"]
            exps_value = stat_list[i]["exp"]
            
            # Format SPECIAL stat display
            stat_display = f"{special_name[0]}: {stats_value}"
            if mods_value != 0:
                stat_display += f"(+{mods_value})"
            special_display.append(stat_display)
            
            cursor.execute("""
               INSERT OR REPLACE INTO Stats
              (dweller_id, StatName, Value, Mod, Exp)
              VALUES (?, ?, ?, ?, ?)
              """, (serialize_id, special_name, stats_value, mods_value, exps_value))
        
        print(f"  SPECIAL: {' | '.join(special_display)}")

        # Find dweller's room assignment
        current_room = None
        for room in rooms:
            for dweller_id in room.get("dwellers", []):
                if serialize_id == dweller_id:
                    current_room = room.get('type')
                    print(f"  Assignment: {current_room}")
                    
                    cursor.execute("""
                    INSERT OR REPLACE INTO dwellers
                    (dweller_id, Fullname, CurrentHealth, MaxHealth, [Level], Outfit, CurrentRoom)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (serialize_id, fullname, health, maxhealth, lvl, outfitId, current_room))
                    break
            if current_room:
                break
        
        if not current_room:
            print(f"  Assignment: Not assigned to any room")

        # Track weapon and outfit
        weaponId = weapon.get("id")
        print(f"  Weapon: {weaponId if weaponId else 'None'}")
        
        if weaponId:
            weapon_list.append(weaponId)

        if outfitId:
            outfit_list.append(outfitId)

        conn.commit()
        dwellercount += 1

    # Process rooms
    print_section("PROCESSING ROOMS")
    
    room_types = {}
    for roominfo in rooms:
        names = [] 
        dwellerid = []
        DeserializedID = roominfo.get("deserializeID")
        Roomtype = roominfo.get("type")
        Class = roominfo.get("class")
        Row = roominfo.get("row")
        Column = roominfo.get("col")
        Roomlevel = roominfo.get("level")
        MergeLevel = roominfo.get("mergeLevel")

        # Track room types for summary
        room_types[Roomtype] = room_types.get(Roomtype, 0) + 1

        # Determine room size based on merge level
        size_map = {0: "Small", 1: "Medium", 2: "Large"}
        size = size_map.get(MergeLevel, "Unknown")

        print(f"\n{Roomtype} ({Class})")
        print(f"  Location: Row {Row}, Col {Column}")
        print(f"  Level: {Roomlevel} | Size: {size} (Merge {MergeLevel})")

        # Get dwellers in room
        for dweller_id in roominfo.get("dwellers", []):
            cursor.execute("SELECT Fullname FROM dwellers WHERE dweller_id = ?", (dweller_id,))
            row = cursor.fetchone()
            if row and row[0] is not None:
                names.append(row[0])
                dwellerid.append(dweller_id)
            else:
                names.append(f"ID {dweller_id} (missing)")

        if names:
            print(f"  Dwellers ({len(names)}): {', '.join(names)}")
        else:
            print(f"  Dwellers: None")

        table_name = table_map.get(roominfo.get("class"), "Non_ProductionRoom")

        sql = f"""
        INSERT OR REPLACE INTO {table_name}
        (Room_id, RoomName, RoomClass, Row, Column, RoomLevel, MergeLevel, DwellerAssigned, dweller_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            DeserializedID, Roomtype, Class, Row, Column,
            Roomlevel, MergeLevel, ", ".join(names), ", ".join(map(str, dwellerid))
        )

        cursor.execute(sql, params)
        conn.commit()

    # Process storage items
    print_section("PROCESSING STORAGE")
    
    for item in storItems:
        itemId = item.get("id")
        itemType = item.get("type")
        isAssigned = item.get("hasBeenAssigned")
   
        if itemType == "Outfit":
            oCounter += 1 
            outfit_list.append(itemId)

        elif itemType == "Weapon":
            wCounter += 1
            weapon_list.append(itemId)

        else:
            jCounter
            jCounter += 1
    
    print(f"Storage Items Summary:")
    print(f"  Weapons: {wCounter}")
    print(f"  Outfits: {oCounter}")
    print(f"  Junk: {jCounter}")

    # Final summary
    print_section("PROCESSING COMPLETE")
    
    print(f"Summary:")
    print(f"  ✓ Processed {dwellercount} dwellers")
    print(f"  ✓ Processed {len(rooms)} rooms")
    if delcount > 0:
        print(f"  ✓ Cleaned up {delcount} deleted dweller(s)")
    
    print(f"\nRoom Distribution:")
    for room_type, count in sorted(room_types.items()):
        print(f"  {room_type}: {count}")

    print(f"\nOutfit Tracking:")
    unique_outfits = set(outfit_list)
    print(f"  Total outfits (equipped + storage): {len(outfit_list)}")
    print(f"  Unique outfit types: {len(unique_outfits)}")
    
    if unique_outfits:
        print(f"\n  Outfit IDs in use:")
        for outfit in sorted(unique_outfits):
            count = outfit_list.count(outfit)
            print(f"    {outfit}: {count}x")

    conn.close()
    print(f"\n{'=' * 80}\n")
    
    return outfit_list

import subprocess
import time
import os
import json
import sqlite3
from typing import Collection
import pyodbc


def run(json_path):
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()

    wCounter = 0
    oCounter = 0 
    jCounter = 0

    SPECIAL = ["Luck", "Strength", "Perception", "Intelligence", "Chrisma", "Endurance", "Agility"]
    delcount =0
    dwellercount =0

    downloads_folder = os.path.expanduser(r"~\Downloads")
    file_path = os.path.join(downloads_folder, json_path) 

    # Open and read the JSON file
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)


    dwellers_list = data["dwellers"]["dwellers"]
    rooms = data["vault"]["rooms"]
    storItems = data["vault"]["inventory"]["items"]
    outfit_list = []


    json_ids = {d["serializeId"] for d in dwellers_list}
    cursor.execute("SELECT dweller_id FROM dwellers")
    db_ids = {row[0] for row in cursor.fetchall()}
    ids_to_delete = db_ids - json_ids
    for bad_id in ids_to_delete:
        cursor.execute("DELETE FROM Stats WHERE dweller_id = ?", (bad_id,))
        cursor.execute("DELETE FROM dwellers WHERE dweller_id = ?", (bad_id,))
        delcount = delcount +1
    conn.commit()

    tables = ["Stats","TrainingRoom","CraftingRoom","ConsumableRoom","Non_ProductionRoom","ProductionRoom"]
    for t in tables:
        cursor.execute(f"DELETE FROM {t}")
    conn.commit()

    table_map = {
        "Production": "ProductionRoom",
        "Consumable": "ConsumableRoom",
        "Crafting": "CraftingRoom",
        "Training": "TrainingRoom"
    }

    for d in dwellers_list:
        fullname = d.get("name", "") + " " + d.get("lastName", "")
        serialize_id = d.get("serializeId")
        outfit = d.get("equipedOutfit", {})
        outfitId = outfit.get("id")
        h =  d.get("health", {})
        health = h.get("healthValue")
        maxhealth = h.get("maxHealth")
        exp =  d.get("experience", {})
        lvl = exp.get("currentLevel")
        stats_container = d.get("stats", {})
        weapon = d.get("equipedWeapon", {})
        outfit = d.get("equipedOutfit", {})


        stat_list = stats_container["stats"]
        for i, special_name in enumerate(SPECIAL):
            stats_value = stat_list[i]["value"]
            mods_value = stat_list[i]["mod"]
            exps_value = stat_list[i]["exp"]
            print(f"{fullname}(Health: {health}/{maxhealth}, Current level = {lvl}) - (is wearing {outfitId}) - {serialize_id}, {special_name}: {stats_value} - mod = {mods_value}(exps:{exps_value})")
        
            cursor.execute("""
               INSERT OR REPLACE INTO Stats
              (dweller_id, StatName, Value, Mod, Exp)
              VALUES (?, ?, ?, ?, ?)
              """, (serialize_id, special_name, stats_value, mods_value, exps_value))

    
        for room in rooms:
            for dweller_id in room.get("dwellers", []):
                if serialize_id == dweller_id:
                    fullname_with_room = f"{fullname} is working at the {room.get('type')}"
                    print(fullname_with_room)

                    cursor.execute("""
                    INSERT OR REPLACE INTO dwellers
                    (dweller_id, Fullname, CurrentHealth, MaxHealth, [Level], Outfit, CurrentRoom)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (serialize_id, fullname, health, maxhealth, lvl, outfitId, room.get('type')))
                    break
    
        weaponId = weapon.get("id")
        isAssigned = weapon.get("hasBeenAssigned")
        print(f" - Weapon in use: {weaponId}")

        outfitId = outfit.get("id")
        isAssigned = outfit.get("hasBeenAssigned")
        print(f" - Outfit in use: {outfitId}")
        outfit_list.append(outfitId)
       
        print("Dweller Outfit")
        print(f" {fullname} - Outfit ID: {outfitId}")

        conn.commit()
        cursor.execute("SELECT * FROM Stats WHERE dweller_id = ?", (serialize_id,))
        print(cursor.fetchall())
        print("Saved:", fullname, "ID:", serialize_id)
        dwellercount = dwellercount +1


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

        print(f"Room {Roomtype} (Class: {Class}) at ({Row},{Column}) - Room Level: {Roomlevel}, Merge Level: {MergeLevel}, ID: {DeserializedID}")

        for dweller_id in roominfo.get("dwellers", []):
            cursor.execute("SELECT Fullname FROM dwellers WHERE dweller_id = ?", (dweller_id,))
            row = cursor.fetchone()
            if row and row[0] is not None:
                names.append(row[0])
                dwellerid.append(dweller_id)
                print(" - Dweller:", row[0])
            else:
                names.append(f"ID {dweller_id} (missing)")
                print(" - Dweller: ID", dweller_id, "(missing)")

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

        result = ", ".join(names)
        print(f"{result} + {dwellerid}")
    conn.close()

    for item in storItems:
    
        itemId = item.get("id")
        itemType = item.get("type")
        isAssigned = item.get("hasBeenAssigned")

   
        if itemType == "Outfit":
            oCounter = oCounter + 1 
            outfit_list.append(itemId)
    
        
    print(f"Total Weapons: {wCounter}, Total Outfits: {oCounter}, Total Junk: {jCounter}")               
    print(f"{delcount} dweller IDs was deleted")
    print(f"{dwellercount} dwellers was processed")
    print("Outfits in use or in storage:")
    for outfit in set(outfit_list):
        print(f" - Outfit ID: {outfit}")


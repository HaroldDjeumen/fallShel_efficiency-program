from collections import defaultdict
import os
import time
import json
import sqlite3
from matplotlib import pyplot as plt
import numpy as np

def run(json_path, outfitlist, vault_name):

    # --- Config / constants ----------------------------------------------------
    conn = sqlite3.connect("vault.db")
    cursor = conn.cursor()

    downloads_folder = os.path.expanduser(r"~\Downloads")
    file_path = os.path.join(downloads_folder, json_path)

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    vault_file = "vault_map.txt"
    dwellers_list = data["dwellers"]["dwellers"]

    ROOM_CODE_MAP = {
        "Geothermal": ("Power", "Strength"),
        "Energy2": ("Power2", "Strength"),
        "WaterPlant": ("Water", "Perception"),
        "Water2": ("Water2", "Perception"),
        "Cafeteria": ("Food", "Agility"),
        "Hydroponic": ("Food2", "Agility")
    }

    ROOM_STAT_MAP = {
        "Geothermal": "Strength",
        "Energy2": "Strength",
        "WaterPlant": "Perception",
        "Water2": "Perception",
        "Cafeteria": "Agility",
        "Hydroponic": "Agility"
    }

    ROOM_GROUPS = {
        "Power": ("Geothermal", "Energy2"),
        "Water": ("WaterPlant", "Water2"),
        "Food": ("Cafeteria", "Hydroponic")
    }

    BASE_POOL = {
        "Power": 1320,
        "Food": 960,
        "Water": 960,
        "Power2": 1800,
        "Food2": 1200,
        "Water2": 1200
    }

    SIZE_MULTIPLIER = {"size3": 1, "size6": 2, "size9": 3}
    ROOM_CAPACITY = {"size3": 2, "size6": 4, "size9": 6}

    # --- Storage ---------------------------------------------------------------
    initial_rooms = {}  # mapping room_key tuple -> list of dweller ids (strings)
    _room_counts = defaultdict(int)

    # --- Load production rooms -------------------------------------------------
    cursor.execute(
        "SELECT dweller_id, RoomName, Row, Column, RoomLevel, MergeLevel FROM ProductionRoom",
    )
    production_rooms = cursor.fetchall()


    def _lvl_str(room_level: int) -> str:
        return f"lvl{room_level if room_level in (1, 2) else 3}"


    def _size_str(merge_level: int) -> str:
        if merge_level == 1:
            return "size3"
        if merge_level == 2:
            return "size6"
        return "size9"


    for dweller_ids, room_name, row, column, room_l, merge_l in production_rooms:
        if room_name not in ROOM_STAT_MAP:
            continue

        dwellers = [x.strip() for x in str(dweller_ids).split(",") if x.strip()]

        base_key = (room_name, _lvl_str(room_l), _size_str(merge_l))
        _room_counts[base_key] += 1
        room_number = str(_room_counts[base_key])
        room_key = (base_key[0], base_key[1], base_key[2], room_number)
        initial_rooms[room_key] = dwellers

    for key, dwellers in initial_rooms.items():
        print(f"Room: {key} -> Dwellers: {', '.join(dwellers)}")

    # --- Parse vault_map.txt into room lists -----------------------------------
    geothermal = []
    waterPlant = []
    cafeteria = []
    gym = []
    armory = []
    dojo = []

    try:
        with open(vault_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(" | ")
                for room in parts:
                    if room == "Empty":
                        continue

                    if "MergeLevel: 3" in room:
                        size_s = "size9"
                    elif "MergeLevel: 2" in room:
                        size_s = "size6"
                    else:
                        size_s = "size3"

                    if "level= 3" in room:
                        lvl = 3
                    elif "level= 2" in room:
                        lvl = 2
                    else:
                        lvl = 1

                    code = None
                    if "Energy2" in room:
                        code = "Energy2"
                    elif "Water2" in room:
                        code = "Water2"
                    elif "Hydroponic" in room:
                        code = "Hydroponic"
                    elif "Geothermal" in room:
                        code = "Geothermal"
                    elif "WaterPlant" in room:
                        code = "WaterPlant"
                    elif "Cafeteria" in room:
                        code = "Cafeteria"
                    elif "Gym" in room:
                        code = "Gym"
                    elif "Armory" in room:
                        code = "Armory"
                    elif "Dojo" in room:
                        code = "Dojo"

                    if not code:
                        continue

                    room_tuple = (code, f"lvl{lvl}", size_s, "1")

                    if code in ("Energy2", "Geothermal"):
                        geothermal.append(room_tuple)
                    elif code in ("WaterPlant", "Water2"):
                        waterPlant.append(room_tuple)
                    elif code in ("Cafeteria", "Hydroponic"):
                        cafeteria.append(room_tuple)
                    elif code == "Gym":
                        gym.append(room_tuple)
                    elif code == "Armory":
                        armory.append(room_tuple)
                    elif code == "Dojo":
                        dojo.append(room_tuple)
    except FileNotFoundError:
        print(f"{vault_file} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


    # --- Normalize room lists: remove repeated tiles after merged rooms -------
    def compact_room_list(lst):
        out = []
        i = 0
        while i < len(lst):
            out.append(lst[i])
            size = lst[i][2]
            if size == "size9":
                i += 9
            elif size == "size6":
                i += 6
            else:
                i += 3
        return out


    RoomLists = [compact_room_list(geothermal), compact_room_list(waterPlant), compact_room_list(cafeteria)]


    def number_duplicates(lst):
        counts = defaultdict(int)
        out = []
        for tup in lst:
            base = (tup[0], tup[1], tup[2])
            counts[base] += 1
            out.append((base[0], base[1], base[2], str(counts[base])))
        return out


    geothermal = number_duplicates(RoomLists[0])
    waterPlant = number_duplicates(RoomLists[1])
    cafeteria = number_duplicates(RoomLists[2])

    # --- Read dweller stats once and build fast lookup -------------------------
    Stats = {}
    dweller_stats = {}
    dweller_stats_initial = {}
    mod_list = {}
    numDwellers = 0
    total_happiness = 0

    for d in dwellers_list:
        serialize_id = d.get("serializeId")
        happiness = d.get("happiness", {}).get("happinessValue", 0)
        numDwellers += 1
        total_happiness += happiness

        cursor.execute(
            "SELECT dweller_id, StatName, Value, Mod FROM Stats WHERE dweller_id = ?",
            (serialize_id,)
        )
        allStats = cursor.fetchall()
        Stats[serialize_id] = allStats

        # storing the stat of each dweller
        stat_map_initial = {statname: value + mode for _dwid, statname, value, mode in allStats}
        stat_map = {statname: value for _dwid, statname, value, mode in allStats}
        dweller_stats[str(serialize_id)] = stat_map
        dweller_stats_initial[str(serialize_id)] = stat_map_initial

    print(f"\nTotal Dwellers: {numDwellers}\n")
    print("Dweller Stats:")
    for dwid in Stats.keys():
        print(f"Dweller ID: {dwid}")
        for stat in Stats[dwid]:
            print(f"  Stat: {stat[1]}, Value: {stat[2]}, Mod: {stat[3]}")
        print("")

    vault_happiness = round(total_happiness / numDwellers) if numDwellers > 0 else 0
    print(f"\nVault Average Happiness: {vault_happiness}%\n")

    # --- Build best/second/worst lists efficiently -----------------------------
    bestGeo = []
    bestWaP = []
    bestCaf = []
    secbestGeo = []
    secbestWaP = []
    secbestCaf = []
    worstGeo = []
    worstWaP = []
    worstCaf = []

    for serialize_id, stats in dweller_stats.items():
        values = {k: v for k, v in stats.items() if k in ("Strength", "Perception", "Agility")}
        if not values:
            continue

        sorted_stats = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
        highest_stat, highest_val = sorted_stats[0]
        second = sorted_stats[1] if len(sorted_stats) > 1 else (None, -1)
        second_stat, second_val = second
        lowest_stat, lowest_val = min(values.items(), key=lambda kv: kv[1])

        if highest_stat == "Strength":
            bestGeo.append(f"{serialize_id} - {highest_val}")
        elif highest_stat == "Perception":
            bestWaP.append(f"{serialize_id} - {highest_val}")
        elif highest_stat == "Agility":
            bestCaf.append(f"{serialize_id} - {highest_val}")

        if second_stat == "Strength":
            secbestGeo.append(f"{serialize_id} - {second_val}")
        elif second_stat == "Perception":
            secbestWaP.append(f"{serialize_id} - {second_val}")
        elif second_stat == "Agility":
            secbestCaf.append(f"{serialize_id} - {second_val}")

        if lowest_stat == "Strength":
            worstGeo.append(f"{serialize_id} - {lowest_val}")
        elif lowest_stat == "Perception":
            worstWaP.append(f"{serialize_id} - {lowest_val}")
        elif lowest_stat == "Agility":
            worstCaf.append(f"{serialize_id} - {lowest_val}")


    # sort lists
    bestGeo.sort(key=lambda s: int(s.split(" - ")[1]), reverse=True)
    bestWaP.sort(key=lambda s: int(s.split(" - ")[1]), reverse=True)
    bestCaf.sort(key=lambda s: int(s.split(" - ")[1]), reverse=True)
    secbestGeo.sort(key=lambda s: int(s.split(" - ")[1]))
    secbestWaP.sort(key=lambda s: int(s.split(" - ")[1]))
    secbestCaf.sort(key=lambda s: int(s.split(" - ")[1]))
    worstGeo.sort(key=lambda s: int(s.split(" - ")[1]))
    worstWaP.sort(key=lambda s: int(s.split(" - ")[1]))
    worstCaf.sort(key=lambda s: int(s.split(" - ")[1]))

    # --- Helper utility functions ----------------------------------------------
    def extract_ids(data):
        return [x.split(" - ")[0].strip() for x in data]


    def get_unassignedID(*lists):
        return [item for sub in lists for item in sub]


    def get_unassigned_stat(stats_list, allowed_ids):
        allowed = set(allowed_ids)
        stats_list[:] = [s for s in stats_list if s.split(" - ")[0].strip() in allowed]


    sortedL = defaultdict(list)


    def assign_rooms(rooms, dwellers):
        size_map = {"size9": 6, "size6": 4, "size3": 2}
        for room in rooms:
            size = room[2]
            limit = size_map.get(size, 0)
            assigned_now = len(sortedL[room])
            take = limit - assigned_now
            if take > 0 and dwellers:
                to_assign = dwellers[:take]
                del dwellers[:take]
                sortedL[room].extend(to_assign)

    # --- Assign dwellers to production rooms (three rounds) --------------------
    geo_dwellers = extract_ids(bestGeo)
    caf_dwellers = extract_ids(bestCaf)
    wap_dwellers = extract_ids(bestWaP)

    sec_geo_dwellers = extract_ids(secbestGeo)
    sec_caf_dwellers = extract_ids(secbestCaf)
    sec_wap_dwellers = extract_ids(secbestWaP)

    thi_geo_dwellers = extract_ids(worstGeo)
    thi_caf_dwellers = extract_ids(worstCaf)
    thi_wap_dwellers = extract_ids(worstWaP)

    # Round 1
    assign_rooms(geothermal, geo_dwellers)
    assign_rooms(waterPlant, wap_dwellers)
    assign_rooms(cafeteria, caf_dwellers)

    # Round 2 (second best)
    secRdwellers = get_unassignedID(sec_geo_dwellers, sec_caf_dwellers, sec_wap_dwellers)
    get_unassigned_stat(secbestGeo, secRdwellers)
    get_unassigned_stat(secbestCaf, secRdwellers)
    get_unassigned_stat(secbestWaP, secRdwellers)
    assign_rooms(geothermal, sec_geo_dwellers)
    assign_rooms(waterPlant, sec_wap_dwellers)
    assign_rooms(cafeteria, sec_caf_dwellers)

    # Round 3 (third / worst)
    thiRdwellers = get_unassignedID(thi_geo_dwellers, thi_caf_dwellers, thi_wap_dwellers)
    get_unassigned_stat(worstGeo, thiRdwellers)
    get_unassigned_stat(worstCaf, thiRdwellers)
    get_unassigned_stat(worstWaP, thiRdwellers)
    assign_rooms(geothermal, thi_geo_dwellers)
    assign_rooms(waterPlant, thi_wap_dwellers)
    assign_rooms(cafeteria, thi_caf_dwellers)

    # Left-over
    leftOver = get_unassignedID(thi_geo_dwellers, thi_caf_dwellers, thi_wap_dwellers)

    print("")
    for room, dwellers in sortedL.items():
        print(f"Room: {room} -> Dwellers: {', '.join(dwellers)}")
    print("")

    # --- Training assignments ---------------------------------------------------
    get_unassigned_stat(worstGeo, leftOver)
    get_unassigned_stat(worstCaf, leftOver)
    get_unassigned_stat(worstWaP, leftOver)

    for lst in (worstGeo, worstCaf, worstWaP):
        lst.sort(key=lambda x: int(x.split(" - ")[1]))

    assign_rooms(gym, extract_ids(worstGeo))
    assign_rooms(dojo, extract_ids(worstCaf))
    assign_rooms(armory, extract_ids(worstWaP))

    # second round training
    get_unassigned_stat(secbestGeo, leftOver)
    get_unassigned_stat(secbestCaf, leftOver)
    get_unassigned_stat(secbestWaP, leftOver)

    for lst in (secbestGeo, secbestCaf, secbestWaP):
        lst.sort(key=lambda x: int(x.split(" - ")[1]))

    assign_rooms(gym, extract_ids(secbestGeo))
    assign_rooms(dojo, extract_ids(secbestCaf))
    assign_rooms(armory, extract_ids(secbestWaP))

    # third round training
    get_unassigned_stat(bestGeo, leftOver)
    get_unassigned_stat(bestCaf, leftOver)
    get_unassigned_stat(bestWaP, leftOver)

    for lst in (bestGeo, bestCaf, bestWaP):
        lst.sort(key=lambda x: int(x.split(" - ")[1]))

    assign_rooms(gym, extract_ids(bestGeo))
    assign_rooms(dojo, extract_ids(bestCaf))
    assign_rooms(armory, extract_ids(bestWaP))

    print("\nTraining Rooms:")
    for room, dwellers in sortedL.items():
        if room[0] in ("Gym", "Armory", "Dojo"):
            print(f"Room: {room} -> Dwellers: {', '.join(dwellers)}")
    print("")

    allDwellerIDs = {str(d["serializeId"]) for d in dwellers_list}
    assigned = set()
    for dwellers in sortedL.values():
        assigned.update(dwellers)
    finalRemaining = list(allDwellerIDs - assigned)

    print("\nFinal Unassigned Dwellers:")
    print(", ".join(finalRemaining))

    # --- Production time helpers -----------------------------------------------
    def parse_room(room_key):
        code = room_key[0]
        size = room_key[2]
        room_type, stat = ROOM_CODE_MAP.get(code, (None, None))
        return room_type, stat, size


    def get_room_production_time(room_key, dwellers, dweller_stats, happiness=1.0):
        room_type, stat, size = parse_room(room_key)
        if room_type is None or not dwellers:
            return None
        pool = BASE_POOL[room_type] * SIZE_MULTIPLIER[size]


        total_stat = sum(dweller_stats.get(d, {}).get(stat, 0) for d in dwellers)
        if total_stat == 0:
            return None
        return round(pool / (total_stat * happiness), 1)


    initial_mean_finder = {}
    mean_finder = {}

    print("\nTIME BEFORE ANY CHANGES")
    for room_key, dwellers in initial_rooms.items():
        t = get_room_production_time(room_key, dwellers, dweller_stats_initial, happiness=vault_happiness/100)
        if t:
            initial_mean_finder[room_key] = t
            print(f"{room_key} -> {t} seconds")

    print("\nTIME")
    for room_key, dwellers in sortedL.items():
        t = get_room_production_time(room_key, dwellers, dweller_stats, happiness=vault_happiness/100)
        if t:
            mean_finder[room_key] = t
            print(f"{room_key} -> {t} seconds")


    # --- Compute group means once (safety guards) -------------------------------
    def group_means(mean_map):
        geo = [t for r, t in mean_map.items() if r[0] in ("Geothermal", "Energy2")]
        wap = [t for r, t in mean_map.items() if r[0] in ("WaterPlant", "Water2")]
        caf = [t for r, t in mean_map.items() if r[0] in ("Cafeteria", "Hydroponic")]
        return (
            (sum(geo) / len(geo)) if geo else None,
            (sum(wap) / len(wap)) if wap else None,
            (sum(caf) / len(caf)) if caf else None,
        )


    geo_mean, wap_mean, caf_mean = group_means(mean_finder)

    if geo_mean is not None:
        print(f"\nGeothermal Average Time: {round(geo_mean,1)} seconds")
    if wap_mean is not None:
        print(f"Water Plant Average Time: {round(wap_mean,1)} seconds")
    if caf_mean is not None:
        print(f"Cafeteria Average Time: {round(caf_mean,1)} seconds")

    # --- STAT ADJUSTMENT SUGGESTIONS -------------------------------------------
    print("\nSTAT ADJUSTMENT SUGGESTIONS")
    for room_key, prod_time in mean_finder.items():
        room_type, stat, size = parse_room(room_key)
        if room_type is None:
            continue
        if room_type == "Power":
            target = geo_mean
        elif room_type == "Water":
            target = wap_mean
        elif room_type == "Food":
            target = caf_mean
        else:
            continue
        pool = BASE_POOL[room_type] * SIZE_MULTIPLIER[size]
        dwellers = sortedL[room_key]
        current_total = sum(dweller_stats.get(d, {}).get(stat, 0) for d in dwellers)
        if not target:
            continue
        ideal_total = pool / (target * (vault_happiness / 100))
        diff = round(ideal_total - current_total, 1)
        if abs(diff) < 0.5:
            status = "Balanced"
        elif diff > 0:
            status = f"Needs +{diff} {stat}"
        else:
            status = f"Remove {abs(diff)} {stat}"
        print(f"{room_key} | Time: {prod_time}s | {status}")

    # --- Auto-balancing (limited passes, efficient selection) -------------------
    TRAINING_ROOMS = {"Armory", "Dojo", "Gym"}
    BALANCE_THRESHOLD = 5.0
    MAX_PASSES = 10


    def recalc_mean_finder():
        mean_finder.clear()
        for room_key, dwellers in sortedL.items():
            t = get_room_production_time(room_key, dwellers, dweller_stats, happiness=vault_happiness / 100)
            if t:
                mean_finder[room_key] = t


    def best_dweller(room_key):
        _, stat, _ = parse_room(room_key)
        return max(sortedL[room_key], key=lambda d: dweller_stats.get(d, {}).get(stat, 0))


    def worst_dweller(room_key):
        _, stat, _ = parse_room(room_key)
        return min(sortedL[room_key], key=lambda d: dweller_stats.get(d, {}).get(stat, 0))

    recalc_mean_finder()
    before_balancing_times = dict(mean_finder)

    for pass_num in range(1, MAX_PASSES + 1):
        recalc_mean_finder()
        geo_mean, wap_mean, caf_mean = group_means(mean_finder)
        if not mean_finder:
            break

        def is_balanced_local():
            for r, t in mean_finder.items():
                rtype, _, _ = parse_room(r)
                target = geo_mean if rtype in ("Geothermal", "Energy2") else \
                         wap_mean if rtype in ("WaterPlant", "Water2") else \
                         caf_mean if rtype in ("Cafeteria", "Hydroponic") else None
                if target is None:
                    continue
                if abs(t - target) > BALANCE_THRESHOLD:
                    return False
            return True

        if is_balanced_local():
            print(f"\nBalanced after {pass_num - 1} passes")
            break

        print(f"\nBALANCE PASS {pass_num}")

        for room_type, codes in ROOM_GROUPS.items():
            rooms = [r for r in mean_finder if r[0] in codes and r[0] not in TRAINING_ROOMS]
            if len(rooms) < 2:
                continue
            weakest = max(rooms, key=lambda r: mean_finder[r])
            strongest = min(rooms, key=lambda r: mean_finder[r])
            if weakest == strongest:
                continue
            if weakest[0] in TRAINING_ROOMS or strongest[0] in TRAINING_ROOMS:
                continue

            if sortedL.get(strongest) and sortedL.get(weakest):
                give = best_dweller(strongest)
                take = worst_dweller(weakest)
                sortedL[strongest].remove(give)
                sortedL[weakest].remove(take)
                sortedL[strongest].append(take)
                sortedL[weakest].append(give)
                print(f"Swapped {give} ↔ {take} between {strongest} and {weakest}")
            elif sortedL.get(strongest):
                mover = best_dweller(strongest)
                sortedL[strongest].remove(mover)
                sortedL[weakest].append(mover)
                print(f"Moved {mover} from {strongest} → {weakest}")
            elif finalRemaining:
                mover = finalRemaining.pop(0)
                sortedL[weakest].append(mover)
                print(f"Assigned {mover} → {weakest}")

    # --- Print final mapping and compute times ---------------------------------
    print("")
    for room, dwellers in sortedL.items():
        print(f"Room: {room} -> Dwellers: {', '.join(dwellers)}")
    print("")

    recalc_mean_finder()
    after_balancing_times = dict(mean_finder)
    mean_finder.clear()

    print("\nFINAL TIMES AFTER BALANCING")
    for room_key, dwellers in sortedL.items():
        t = get_room_production_time(room_key, dwellers, dweller_stats, happiness=vault_happiness/100)
        if t:
            mean_finder[room_key] = t
            print(f"{room_key} -> {t} seconds")


    # --- Further Improvement by using outfit mods ------------------
    print("\n" + "="*60)
    print("OUTFIT OPTIMIZATION")
    print("="*60)

    # Get outfit data
    outfit_mods = {}
    for outfit_id in outfitlist:
        cursor.execute(
            "SELECT Name, `Item ID`, S, P, A, Sex FROM Outfit WHERE `Item ID` = ?",
            (outfit_id,)
        )
        result = cursor.fetchone()
        if result:
            name, item_id, s_mod, p_mod, a_mod, sex = result
            outfit_mods[item_id] = {
                'name': name,
                's': s_mod if s_mod is not None else 0,
                'p': p_mod if p_mod is not None else 0,
                'a': a_mod if a_mod is not None else 0,
                'sex': sex
            }

    print(f"\nAvailable Outfits: {len(outfit_mods)}")
    for outfit_id, mods in outfit_mods.items():
        print(f"  {mods['name']}: S+{mods['s']}, P+{mods['p']}, A+{mods['a']}")

    # Create a copy of dweller_stats to apply outfit mods
    dweller_stats_with_outfits = {k: v.copy() for k, v in dweller_stats.items()}

    # Track outfit assignments
    outfit_assignments = {}  # dweller_id -> outfit_id

    # Calculate current room needs (how much each room deviates from average)
    room_needs = {}
    for room_key, prod_time in mean_finder.items():
        room_type, stat, size = parse_room(room_key)
        if room_type is None or room_key[0] in TRAINING_ROOMS:
            continue
    
        # Get target time
        if room_type in ("Power", "Power2"):
            target = geo_mean
        elif room_type in ("Water", "Water2"):
            target = wap_mean
        elif room_type in ("Food", "Food2"):
            target = caf_mean
        else:
            continue
    
        if target is None:
            continue
    
        # Calculate how much stat is needed to reach target
        pool = BASE_POOL[room_type] * SIZE_MULTIPLIER[size]
        dwellers = sortedL[room_key]
        current_total = sum(dweller_stats.get(d, {}).get(stat, 0) for d in dwellers)
        ideal_total = pool / (target * (vault_happiness / 100))
        stat_deficit = ideal_total - current_total
    
        room_needs[room_key] = {
            'stat': stat,
            'deficit': stat_deficit,
            'current_time': prod_time,
            'target_time': target,
            'dwellers': dwellers,
            'size': size
        }

    # Sort rooms by deficit (prioritize rooms that need the most help)
    sorted_rooms = sorted(room_needs.items(), key=lambda x: x[1]['deficit'], reverse=True)

    # Assign outfits to maximize impact
    available_outfits = list(outfit_mods.keys())

    print("\n" + "-"*60)
    print("OUTFIT ASSIGNMENT STRATEGY - PHASE 1: BALANCING")
    print("-"*60)

    for room_key, need_data in sorted_rooms:
        stat_needed = need_data['stat']
        deficit = need_data['deficit']
        dwellers = need_data['dwellers']
    
        if deficit <= 0:
            print(f"\n{room_key} is already balanced or overcapacity")
            continue
    
        print(f"\n{room_key} needs +{round(deficit, 1)} {stat_needed}")
    
        # Find best outfits for this stat
        outfit_stat_map = {'Strength': 's', 'Perception': 'p', 'Agility': 'a'}
        stat_key = outfit_stat_map.get(stat_needed)
    
        if not stat_key or not available_outfits:
            continue
    
        # Sort available outfits by their bonus for the needed stat
        # Filter out outfits with 0 bonus for the needed stat
        relevant_outfits = [
            oid for oid in available_outfits 
            if outfit_mods[oid][stat_key] > 0
        ]
    
        if not relevant_outfits:
            print(f"  No outfits available with {stat_needed} bonus")
            continue
    
        best_outfits = sorted(
            relevant_outfits,
            key=lambda oid: outfit_mods[oid][stat_key],
            reverse=True
        )
    
        # Assign outfits to dwellers with lowest base stats in this room
        dwellers_sorted = sorted(
            dwellers,
            key=lambda d: dweller_stats.get(d, {}).get(stat_needed, 0)
        )
    
        assigned_count = 0
        for dweller_id in dwellers_sorted:
            if not best_outfits:
                break
        
            # Skip if dweller already has an outfit
            if dweller_id in outfit_assignments:
                continue
        
            # Take the best available outfit
            outfit_id = best_outfits.pop(0)
            available_outfits.remove(outfit_id)
        
            # Assign outfit to dweller
            outfit_assignments[dweller_id] = outfit_id
        
            # Apply outfit mods to dweller stats
            dweller_stats_with_outfits[dweller_id]['Strength'] += outfit_mods[outfit_id]['s']
            dweller_stats_with_outfits[dweller_id]['Perception'] += outfit_mods[outfit_id]['p']
            dweller_stats_with_outfits[dweller_id]['Agility'] += outfit_mods[outfit_id]['a']
        
            assigned_count += 1
            print(f"  Assigned {outfit_mods[outfit_id]['name']} (+{outfit_mods[outfit_id][stat_key]} {stat_needed}) to Dweller {dweller_id}")
        
            deficit -= outfit_mods[outfit_id][stat_key]
            if deficit <= 0:
                print(f"  ✓ Room balanced!")
                break
    
        if assigned_count == 0:
            print(f"  No suitable outfits available")

    # PHASE 2: Assign remaining outfits to big rooms
    if available_outfits:
        print("\n" + "-"*60)
        print("OUTFIT ASSIGNMENT STRATEGY - PHASE 2: BIG ROOMS")
        print("-"*60)
        print(f"\n{len(available_outfits)} outfits remaining - assigning to largest rooms")
    
        # Get production rooms sorted by size (largest first)
        production_rooms = [
            (room_key, need_data) 
            for room_key, need_data in room_needs.items()
        ]
    
        # Sort by room size priority: size9 > size6 > size3
        size_priority = {'size9': 3, 'size6': 2, 'size3': 1}
        production_rooms.sort(
            key=lambda x: size_priority.get(x[1]['size'], 0),
            reverse=True
        )
    
        for room_key, need_data in production_rooms:
            if not available_outfits:
                break
        
            stat_needed = need_data['stat']
            dwellers = need_data['dwellers']
            size = need_data['size']
        
            print(f"\nAssigning to {room_key} ({size}):")
        
            # Get dwellers in this room that don't have outfits yet
            unequipped_dwellers = [d for d in dwellers if d not in outfit_assignments]
        
            if not unequipped_dwellers:
                print(f"  All dwellers already equipped")
                continue
        
            # Sort dwellers by their stat (lowest first - give them the boost)
            outfit_stat_map = {'Strength': 's', 'Perception': 'p', 'Agility': 'a'}
            stat_key = outfit_stat_map.get(stat_needed)
        
            unequipped_dwellers.sort(
                key=lambda d: dweller_stats.get(d, {}).get(stat_needed, 0)
            )
        
            # Assign best remaining outfits to these dwellers
            for dweller_id in unequipped_dwellers:
                if not available_outfits:
                    break
            
                # Find best outfit for this room's stat from remaining outfits
                best_outfit = max(
                    available_outfits,
                    key=lambda oid: outfit_mods[oid][stat_key]
                )
            
                # Assign the outfit
                outfit_assignments[dweller_id] = best_outfit
                available_outfits.remove(best_outfit)
            
                # Apply outfit mods
                dweller_stats_with_outfits[dweller_id]['Strength'] += outfit_mods[best_outfit]['s']
                dweller_stats_with_outfits[dweller_id]['Perception'] += outfit_mods[best_outfit]['p']
                dweller_stats_with_outfits[dweller_id]['Agility'] += outfit_mods[best_outfit]['a']
            
                print(f"  Assigned {outfit_mods[best_outfit]['name']} (+{outfit_mods[best_outfit][stat_key]} {stat_needed}) to Dweller {dweller_id}")

    # Recalculate production times with outfits
    mean_finder_with_outfits = {}
    print("\n" + "="*60)
    print("PRODUCTION TIMES WITH OUTFITS")
    print("="*60)

    for room_key, dwellers in sortedL.items():
        if room_key[0] in TRAINING_ROOMS:
            continue
        t = get_room_production_time(room_key, dwellers, dweller_stats_with_outfits, happiness=vault_happiness/100)
        if t:
            mean_finder_with_outfits[room_key] = t
            old_time = mean_finder.get(room_key, 0)
            improvement = old_time - t
            print(f"{room_key} -> {t}s (was {old_time}s, improved by {round(improvement, 1)}s)")

    # Calculate new averages
    geo_mean_new, wap_mean_new, caf_mean_new = group_means(mean_finder_with_outfits)

    print(f"\n{'='*60}")
    print("AVERAGE TIMES COMPARISON")
    print(f"{'='*60}")

    if geo_mean is not None and geo_mean_new is not None:
        print(f"Power:  {round(geo_mean, 1)}s -> {round(geo_mean_new, 1)}s (Δ {round(geo_mean - geo_mean_new, 1)}s)")
    if wap_mean is not None and wap_mean_new is not None:
        print(f"Water:  {round(wap_mean, 1)}s -> {round(wap_mean_new, 1)}s (Δ {round(wap_mean - wap_mean_new, 1)}s)")
    if caf_mean is not None and caf_mean_new is not None:
        print(f"Food:   {round(caf_mean, 1)}s -> {round(caf_mean_new, 1)}s (Δ {round(caf_mean - caf_mean_new, 1)}s)")

    print(f"\n{'='*60}")
    print("OUTFIT ASSIGNMENT SUMMARY")
    print(f"{'='*60}")
    print(f"Total outfits assigned: {len(outfit_assignments)}")
    print(f"Remaining unassigned outfits: {len(available_outfits)}")

    if outfit_assignments:
        print("\nAssigned Outfits by Room:")
        for room_key, dwellers in sortedL.items():
            if room_key[0] in TRAINING_ROOMS:
                continue
            room_outfits = [(d, outfit_assignments.get(d)) for d in dwellers if d in outfit_assignments]
            if room_outfits:
                print(f"\n{room_key}:")
                for dweller_id, outfit_id in room_outfits:
                    outfit = outfit_mods[outfit_id]
                    print(f"  Dweller {dweller_id} -> {outfit['name']} (S+{outfit['s']}, P+{outfit['p']}, A+{outfit['a']})")
    else:
        print("No outfits were assigned (all rooms already balanced)")

    if available_outfits:
        print(f"\nUnassigned outfits ({len(available_outfits)}):")
        for outfit_id in available_outfits:
            outfit = outfit_mods[outfit_id]
            print(f"  {outfit['name']} (S+{outfit['s']}, P+{outfit['p']}, A+{outfit['a']})")

    # --- Prepare arrays for plotting (exclude training rooms) ------------------
    exclude = {"Gym", "Armory", "Dojo"}
    rooms = [r for r in list(before_balancing_times.keys()) if r[0] not in exclude]

    initial_times = {r: initial_mean_finder.get(r) for r in rooms}
    before_times = {r: before_balancing_times.get(r) for r in rooms}
    after_times = {r: after_balancing_times.get(r) for r in rooms}
    outfit_times = {r: mean_finder_with_outfits.get(r) for r in rooms}

    initial = [np.nan if initial_times.get(r) is None else initial_times[r] for r in rooms]
    before = [np.nan if before_times.get(r) is None else before_times[r] for r in rooms]
    after = [np.nan if after_times.get(r) is None else after_times[r] for r in rooms]
    with_outfits = [np.nan if outfit_times.get(r) is None else outfit_times[r] for r in rooms]

    initial_arr = np.array(initial, dtype=float)
    before_arr = np.array(before, dtype=float)
    after_arr = np.array(after, dtype=float)
    outfit_arr = np.array(with_outfits, dtype=float)

    x = np.arange(len(rooms))
    width = 0.2  

    plt.figure(figsize=(14, 7))  
    plt.bar(x - 1.5*width, initial_arr, width=width, label="Initial", color='#ff6b6b')
    plt.bar(x - 0.5*width, before_arr, width=width, label="Before Balancing", color='#feca57')
    plt.bar(x + 0.5*width, after_arr, width=width, label="After Balancing", color='#48dbfb')
    plt.bar(x + 1.5*width, outfit_arr, width=width, label="With Outfits", color='#1dd1a1')

    plt.xticks(ticks=x, labels=[f"{r[0]}-{r[1]}-{r[2]}-{r[3]}" for r in rooms], rotation=45, ha="right")
    plt.ylabel("Production Time (s)")
    plt.title("Room Production Times: Initial → Balanced → Optimized with Outfits")
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    plot_filename = f"vault_production_{timestamp}.png"
    plt.savefig(plot_filename, dpi=150, bbox_inches='tight')
    plt.close()  # Close the figure to free memory
    print(f"\nPlot saved as: {plot_filename}")


    from VaultPerformanceTracker import VaultPerformanceTracker

    def calculate_overall_average(mean_map):
        """Calculate overall average across all production rooms"""
        times = [t for r, t in mean_map.items() if r[0] not in {"Gym", "Armory", "Dojo"}]
        return round(sum(times) / len(times), 2) if times else 0

    initial_overall = calculate_overall_average(initial_mean_finder)
    before_balance_overall = calculate_overall_average(before_balancing_times)
    after_balance_overall = calculate_overall_average(after_balancing_times)
    with_outfits_overall = calculate_overall_average(mean_finder_with_outfits)

    # Track performance (records data)
    tracker = VaultPerformanceTracker(vault_name)
    tracker.add_cycle_data(
        initial_avg=initial_overall,
        before_balance_avg=before_balance_overall,
        after_balance_avg=after_balance_overall,
        with_outfits_avg=with_outfits_overall
    )

    conn.close()

    


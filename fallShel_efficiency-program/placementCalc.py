from asyncio.windows_events import NULL
from collections import defaultdict
import os
import time
import json
import sqlite3
from matplotlib import pyplot as plt
import numpy as np
from datetime import datetime

def run(json_path, outfitlist, vault_name, optimizer_params=None):
    def print_section(title, char="=", width=100):
        """Print a formatted section header"""
        print(f"\n{char * width}")
        print(f"{title.center(width)}")
        print(f"{char * width}\n")

    def print_subsection(title, width=100):
        """Print a formatted subsection header"""
        print(f"\n{'-' * width}")
        print(f"  {title}")
        print(f"{'-' * width}")
    
    # ===== ADAPTIVE PARAMETERS =====
    if optimizer_params:
        BALANCE_THRESHOLD = optimizer_params.get('BALANCE_THRESHOLD', 5.0)
        MAX_PASSES = optimizer_params.get('MAX_PASSES', 10)
        SWAP_AGGRESSIVENESS = optimizer_params.get('SWAP_AGGRESSIVENESS', 1.0)
        MIN_STAT_THRESHOLD = optimizer_params.get('MIN_STAT_THRESHOLD', 5)
        OUTFIT_STRATEGY = optimizer_params.get('OUTFIT_STRATEGY', 'deficit_first')
    else:
        BALANCE_THRESHOLD = 5.0
        MAX_PASSES = 10
        SWAP_AGGRESSIVENESS = 1.0
        MIN_STAT_THRESHOLD = 5
        OUTFIT_STRATEGY = 'deficit_first'

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
    initial_rooms = {}
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

    total_rooms = len(geothermal) + len(waterPlant) + len(cafeteria)
    is_small_vault = total_rooms < 10

    if is_small_vault:
        print("\n🏠 Small vault detected - using conservative optimization")
        BALANCE_THRESHOLD = 10.0  
        MAX_PASSES = 5
    # --- Read dweller stats once and build fast lookup -------------------------
    Stats = {}
    dweller_stats = {}
    dweller_stats_initial = {}
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

    # --- Assign dwellers to production rooms -----------------------------------
    geo_dwellers = extract_ids(bestGeo)
    caf_dwellers = extract_ids(bestCaf)
    wap_dwellers = extract_ids(bestWaP)

    if MIN_STAT_THRESHOLD > 0:
        geo_dwellers = [d for d in geo_dwellers if dweller_stats.get(d, {}).get('Strength', 0) >= MIN_STAT_THRESHOLD]
        wap_dwellers = [d for d in wap_dwellers if dweller_stats.get(d, {}).get('Perception', 0) >= MIN_STAT_THRESHOLD]
        caf_dwellers = [d for d in caf_dwellers if dweller_stats.get(d, {}).get('Agility', 0) >= MIN_STAT_THRESHOLD]

    sec_geo_dwellers = extract_ids(secbestGeo)
    sec_caf_dwellers = extract_ids(secbestCaf)
    sec_wap_dwellers = extract_ids(secbestWaP)

    thi_geo_dwellers = extract_ids(worstGeo)
    thi_caf_dwellers = extract_ids(worstCaf)
    thi_wap_dwellers = extract_ids(worstWaP)

    # Room priority scoring
    def room_priority_score(room_tuple):
        level_scores = {'lvl3': 3, 'lvl2': 2, 'lvl1': 1}
        size_scores = {'size9': 9, 'size6': 6, 'size3': 3}
        level = level_scores.get(room_tuple[1], 1)
        size = size_scores.get(room_tuple[2], 1)
        level_weight = 2.1 ** (level - 1)
        return level_weight * size

    geothermal_sorted = sorted(geothermal, key=room_priority_score, reverse=True)
    waterPlant_sorted = sorted(waterPlant, key=room_priority_score, reverse=True)
    cafeteria_sorted = sorted(cafeteria, key=room_priority_score, reverse=True)

    print("\n🎯 ROOM ASSIGNMENT PRIORITY ORDER:")
    print(f"Power rooms: {[f'{r[0]} {r[1]} {r[2]}' for r in geothermal_sorted]}")
    print(f"Water rooms: {[f'{r[0]} {r[1]} {r[2]}' for r in waterPlant_sorted]}")
    print(f"Food rooms: {[f'{r[0]} {r[1]} {r[2]}' for r in cafeteria_sorted]}")

    # Round 1
    assign_rooms(geothermal_sorted, geo_dwellers)
    assign_rooms(waterPlant_sorted, wap_dwellers)
    assign_rooms(cafeteria_sorted, caf_dwellers)

    # Round 2
    secRdwellers = get_unassignedID(sec_geo_dwellers, sec_caf_dwellers, sec_wap_dwellers)
    get_unassigned_stat(secbestGeo, secRdwellers)
    get_unassigned_stat(secbestCaf, secRdwellers)
    get_unassigned_stat(secbestWaP, secRdwellers)
    assign_rooms(geothermal, sec_geo_dwellers)
    assign_rooms(waterPlant, sec_wap_dwellers)
    assign_rooms(cafeteria, sec_caf_dwellers)

    # Round 3
    thiRdwellers = get_unassignedID(thi_geo_dwellers, thi_caf_dwellers, thi_wap_dwellers)
    get_unassigned_stat(worstGeo, thiRdwellers)
    get_unassigned_stat(worstCaf, thiRdwellers)
    get_unassigned_stat(worstWaP, thiRdwellers)
    assign_rooms(geothermal, thi_geo_dwellers)
    assign_rooms(waterPlant, thi_wap_dwellers)
    assign_rooms(cafeteria, thi_caf_dwellers)

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

    get_unassigned_stat(secbestGeo, leftOver)
    get_unassigned_stat(secbestCaf, leftOver)
    get_unassigned_stat(secbestWaP, leftOver)

    for lst in (secbestGeo, secbestCaf, secbestWaP):
        lst.sort(key=lambda x: int(x.split(" - ")[1]))

    assign_rooms(gym, extract_ids(secbestGeo))
    assign_rooms(dojo, extract_ids(secbestCaf))
    assign_rooms(armory, extract_ids(secbestWaP))

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
    TRAINING_ROOMS = {"Armory", "Dojo", "Gym"}

    def parse_room(room_key):
        code = room_key[0]
        size = room_key[2]
        room_type, stat = ROOM_CODE_MAP.get(code, (None, None))
        return room_type, stat, size

    def calculate_modifier(merge_size, tier):
        R = merge_size
        merge_factor = 2.1 ** (R - 1)
        stat_factor = 0.9 + (0.1 * tier)
        modifier = merge_factor * stat_factor
        value = int(modifier * 10) / 10
        return value

    def get_room_production_time(room_key, dwellers, dweller_stats, happiness=1.0):
        room_type, stat, size = parse_room(room_key)
        if room_type is None or not dwellers:
            return None

        room_name = room_key[0]
        level_str = room_key[1]
        room_tier = int(level_str.replace("lvl", ""))
        if room_tier == 3:
            tier = 6
        elif room_tier == 2:
            tier = 3
        else:
            tier = 1

        size_str = room_key[2]
        if size_str == "size3":
            merge_size = 1 
        elif size_str == "size6":
            merge_size = 2  
        elif size_str == "size9":
            merge_size = 3  

        pool = BASE_POOL[room_type] * SIZE_MULTIPLIER[size_str]
        total_stat = sum(dweller_stats.get(d, {}).get(stat, 0) for d in dwellers)

        if total_stat == 0:
            return None

        modifier = calculate_modifier(merge_size, tier)

        production_time = 0
        pool_percentage = (pool * (modifier/100)) 

        """ if room_name in ("Cafeteria"):
            production_time = ((pool - pool_percentage) / ((total_stat * happiness) + modifier))- total_stat
        elif room_name in ("WaterPlant"):
            production_time = ((pool - pool_percentage) / (total_stat * happiness))- (4 * total_stat)
        elif room_name in ("Geothermal"):
            production_time = ((pool - pool_percentage) / (total_stat * happiness))- total_stat"""
        production_time = pool/(total_stat * happiness)

        return round(production_time, 1)

    def recalc_mean_finder(stats_dict, sortList):
        """Recalculate mean_finder with current sortedL assignments"""
        result = {}
        for room_key, dwellers in sortList.items():
            t = get_room_production_time(room_key, dwellers, stats_dict, happiness=vault_happiness / 100)
            if t:
                result[room_key] = t
        return result

    def calculate_overall_average(mean_map):
        """Calculate overall average across all production rooms"""
        times = [t for r, t in mean_map.items() if r[0] not in {"Gym", "Armory", "Dojo"}]
        return round(sum(times) / len(times), 2) if times else 0

    def group_means(mean_map):
        geo = [t for r, t in mean_map.items() if r[0] in ("Geothermal", "Energy2")]
        wap = [t for r, t in mean_map.items() if r[0] in ("WaterPlant", "Water2")]
        caf = [t for r, t in mean_map.items() if r[0] in ("Cafeteria", "Hydroponic")]
        return (
            (sum(geo) / len(geo)) if geo else None,
            (sum(wap) / len(wap)) if wap else None,
            (sum(caf) / len(caf)) if caf else None,
        )

    # --- Calculate initial times ---
    print("\nTIME BEFORE ANY CHANGES (INITIAL STATE)")
    initial_mean_finder = recalc_mean_finder(dweller_stats_initial, initial_rooms)
    
    for room_key, t in initial_mean_finder.items():
        level_str = room_key[1]
        room_tier = int(level_str.replace("lvl", ""))
        if room_tier == 3:
            tier = 6
        elif room_tier == 2:
            tier = 3
        else:
            tier = 1

        size_str = room_key[2]
        if size_str == "size3":
            merge_size = 1
        elif size_str == "size6":
            merge_size = 2
        else:
            merge_size = 3
        
        room_type, stat, size = parse_room(room_key)
        dwellers = sortedL[room_key]
        total_stat = sum(dweller_stats_initial.get(d, {}).get(stat, 0) for d in dwellers)
        modifier = calculate_modifier(merge_size, tier)
    
        print(f"{room_key} -> {t}s (Tier:{tier}, Merge:{merge_size}x, Mod:{round(modifier, 2)}, {stat}:{total_stat})")

    print("\nTIME AFTER INITIAL ASSIGNMENT (BEFORE BALANCING)")
    before_balancing_times = recalc_mean_finder(dweller_stats, sortedL)
    
    for room_key, t in before_balancing_times.items():
        print(f"{room_key} -> {t} seconds")

    geo_mean, wap_mean, caf_mean = group_means(before_balancing_times)

    if geo_mean is not None:
        print(f"\nGeothermal Average Time: {round(geo_mean,1)} seconds")
    if wap_mean is not None:
        print(f"Water Plant Average Time: {round(wap_mean,1)} seconds")
    if caf_mean is not None:
        print(f"Cafeteria Average Time: {round(caf_mean,1)} seconds")

    initial_overall_avg = calculate_overall_average(initial_mean_finder)
    before_balance_overall_avg = calculate_overall_average(before_balancing_times)

    print(f"\n{'='*60}")
    print("PERFORMANCE COMPARISON")
    print(f"{'='*60}")
    print(f"Initial Average Time: {initial_overall_avg}s")
    print(f"Before Balancing Average Time: {before_balance_overall_avg}s")

    initial_used = False
    # Determine which state to use as baseline for balancing
    if initial_overall_avg > 0 and initial_overall_avg < before_balance_overall_avg:
        print(f"\n⚠️  Initial assignment ({initial_overall_avg}s) is BETTER than before balancing ({before_balance_overall_avg}s)")
        print(f"    Using INITIAL state as baseline for balancing process")
        sortedL.clear()
        for room_key, dwellers in initial_rooms.items():
            sortedL[room_key] = dwellers.copy()
        working_stats = dweller_stats_initial.copy()
        print(f"    ✓ Balancing will optimize from initial state")
        initial_used = True
    else:
        print(f"\n✓ Before balancing ({before_balance_overall_avg}s) is better than or equal to initial ({initial_overall_avg}s)")
        print(f"    Using BEFORE BALANCING state as baseline")
        working_stats = dweller_stats.copy()

    # --- Auto-balancing ---
    for pass_num in range(1, MAX_PASSES + 1):
        if initial_used == False:
            mean_finder = recalc_mean_finder(working_stats, sortedL)
        else:
            mean_finder = recalc_mean_finder(working_stats, initial_rooms)
        geo_mean, wap_mean, caf_mean = group_means(mean_finder)

        if not mean_finder:
            break

        def is_balanced_local():
            for r, t in mean_finder.items():
                rtype, _, _ = parse_room(r)
                if rtype in ("Power", "Power2"):
                    target = geo_mean
                elif rtype in ("Water", "Water2"):
                    target = wap_mean
                elif rtype in ("Food", "Food2"):
                    target = caf_mean
                else:
                    continue
                if target is None or t is None:
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

            weakest_time = mean_finder.get(weakest)
            strongest_time = mean_finder.get(strongest)

            if weakest_time is None or strongest_time is None:
                continue

            time_diff = weakest_time - strongest_time

            if time_diff < BALANCE_THRESHOLD * 2:
                continue

            _, stat, _ = parse_room(weakest)

            if not sortedL.get(strongest) or not sortedL.get(weakest):
                continue

            best_from_strong = max(sortedL[strongest], 
                                    key=lambda d: working_stats.get(d, {}).get(stat, 0))
            worst_from_weak = min(sortedL[weakest], 
                                    key=lambda d: working_stats.get(d, {}).get(stat, 0))

            best_stat = working_stats.get(best_from_strong, {}).get(stat, 0)
            worst_stat = working_stats.get(worst_from_weak, {}).get(stat, 0)

            if best_stat <= worst_stat * 1.5:
                continue

            sortedL[strongest].remove(best_from_strong)
            sortedL[weakest].remove(worst_from_weak)
            sortedL[strongest].append(worst_from_weak)
            sortedL[weakest].append(best_from_strong)
            print(f"Swapped {best_from_strong} (stat:{best_stat}) ↔ {worst_from_weak} (stat:{worst_stat})")
            print(f"  between {strongest} and {weakest}")

    # --- Final state after balancing ---
    print("")
    for room, dwellers in sortedL.items():
        print(f"Room: {room} -> Dwellers: {', '.join(dwellers)}")
    print("")

    after_balancing_times = recalc_mean_finder(working_stats, sortedL)

    print("\nFINAL TIMES AFTER BALANCING")
    for room_key, t in after_balancing_times.items():
        print(f"{room_key} -> {t} seconds")

    geo_mean, wap_mean, caf_mean = group_means(after_balancing_times)

    if geo_mean is not None:
        print(f"\nGeothermal Average Time: {round(geo_mean,1)} seconds")
    if wap_mean is not None:
        print(f"Water Plant Average Time: {round(wap_mean,1)} seconds")
    if caf_mean is not None:
        print(f"Cafeteria Average Time: {round(caf_mean,1)} seconds")

    # --- OUTFIT OPTIMIZATION ---
    print("\n" + "="*60)
    print("OUTFIT OPTIMIZATION")
    print("="*60)

    # FIX 1: Load existing outfits from database ONCE
    existing_outfit_assignments = {}
    cursor.execute("SELECT dweller_id, Outfit FROM dwellers WHERE Outfit IS NOT NULL AND outfit != ''")
    existing_outfits = cursor.fetchall()

    print(f"\nExisting outfit assignments found: {len(existing_outfits)}")
    for dweller_id, outfit_id in existing_outfits:
        existing_outfit_assignments[str(dweller_id)] = outfit_id
        print(f"  Dweller {dweller_id} already has outfit {outfit_id}")

    # Get outfit data
    outfit_mods = {}
    all_outfit_ids = set(outfitlist) | set(existing_outfit_assignments.values())
    
    for outfit_id in all_outfit_ids:
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

    print(f"\nAvailable Outfits for NEW Assignment: {len(outfitlist)}")
    for outfit_id in outfitlist:
        if outfit_id in outfit_mods:
            mods = outfit_mods[outfit_id]
            print(f"  {mods['name']}: S+{mods['s']}, P+{mods['p']}, A+{mods['a']}")

    # FIX 2: Create a FRESH copy for outfit calculations
    dweller_stats_with_outfits = {k: v.copy() for k, v in working_stats.items()}
    
    # FIX 3: Track assignments properly - start fresh, then add existing
    outfit_assignments = {}
    outfits_to_relocate = []

    # Validate existing outfits
    print("\n" + "-"*60)
    print("VALIDATING EXISTING OUTFIT ASSIGNMENTS")
    print("-"*60)

    outfit_stat_map = {'Strength': 's', 'Perception': 'p', 'Agility': 'a'}

    for dweller_id, outfit_id in existing_outfit_assignments.items():
        dweller_room = None
        for room_key, dwellers in sortedL.items():
            if dweller_id in dwellers:
                dweller_room = room_key
                break
    
        if dweller_room and outfit_id in outfit_mods:
            room_type, stat, size = parse_room(dweller_room)
            outfit = outfit_mods[outfit_id]
            stat_key = outfit_stat_map.get(stat)
        
            if stat_key and outfit[stat_key] > 0:
                # Keep this outfit - it's correctly placed
                outfit_assignments[dweller_id] = outfit_id
                # Apply bonuses ONCE
                dweller_stats_with_outfits[dweller_id]['Strength'] += outfit['s']
                dweller_stats_with_outfits[dweller_id]['Perception'] += outfit['p']
                dweller_stats_with_outfits[dweller_id]['Agility'] += outfit['a']
                print(f"✓ Dweller {dweller_id} in {room_type} room with {outfit['name']} (+{outfit[stat_key]} {stat})")
            else:
                # Mark for relocation
                print(f"⚠️  Dweller {dweller_id} in {room_type} room has MISPLACED {outfit['name']}")
                print(f"    Room needs {stat}, outfit gives: S+{outfit['s']}, P+{outfit['p']}, A+{outfit['a']}")
                outfits_to_relocate.append((dweller_id, outfit_id))

    # Handle relocations
    if outfits_to_relocate:
        print(f"\n⚠️  Found {len(outfits_to_relocate)} misplaced outfits - attempting to relocate...")
    
        for old_dweller_id, outfit_id in outfits_to_relocate:
            outfit = outfit_mods[outfit_id]
            best_stat = max([('Strength', outfit['s']), ('Perception', outfit['p']), ('Agility', outfit['a'])], 
                           key=lambda x: x[1])
            best_stat_name, best_stat_value = best_stat
        
            if best_stat_value == 0:
                continue
        
            found_new_home = False
            for room_key, dwellers in sortedL.items():
                room_type, stat, size = parse_room(room_key)
                if room_key[0] in TRAINING_ROOMS:
                    continue
                if stat == best_stat_name:
                    for potential_dweller in dwellers:
                        if potential_dweller not in outfit_assignments and potential_dweller != old_dweller_id:
                            outfit_assignments[potential_dweller] = outfit_id
                            # Apply bonuses to new dweller
                            dweller_stats_with_outfits[potential_dweller]['Strength'] += outfit['s']
                            dweller_stats_with_outfits[potential_dweller]['Perception'] += outfit['p']
                            dweller_stats_with_outfits[potential_dweller]['Agility'] += outfit['a']
                            print(f"  ✓ Moved {outfit['name']} from Dweller {old_dweller_id} to Dweller {potential_dweller}")
                            found_new_home = True
                            break
                if found_new_home:
                    break

    # Calculate room needs
    room_needs = {}
    current_times = recalc_mean_finder(dweller_stats_with_outfits, sortedL)
    
    for room_key, prod_time in current_times.items():
        room_type, stat, size = parse_room(room_key)
        if room_type is None or room_key[0] in TRAINING_ROOMS:
            continue

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

        pool = BASE_POOL[room_type] * SIZE_MULTIPLIER[size]
        dwellers = sortedL[room_key]
        current_total = sum(dweller_stats_with_outfits.get(d, {}).get(stat, 0) for d in dwellers)
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

    sorted_rooms = sorted(room_needs.items(), key=lambda x: x[1]['deficit'], reverse=True)

    # Track outfit usage
    from collections import Counter
    available_outfits = [oid for oid in outfitlist if oid in outfit_mods and oid not in outfit_assignments.values()]
    outfit_inventory = Counter(available_outfits)
    outfit_used = {oid: 0 for oid in outfit_inventory}

    print(f"\nOutfits available for new assignments: {sum(outfit_inventory.values())}")
    print(f"Outfits already assigned: {len(outfit_assignments)}")

    def outfit_available(outfit_id):
        return outfit_used.get(outfit_id, 0) < outfit_inventory.get(outfit_id, 0)

    def any_outfit_left():
        return any(outfit_used.get(oid, 0) < outfit_inventory.get(oid, 0) for oid in outfit_inventory)

    def get_outfit_bonus_for_stat(outfit_id, stat_name):
        if outfit_id not in outfit_mods:
            return 0
        outfit = outfit_mods[outfit_id]
        stat_key = outfit_stat_map.get(stat_name)
        return outfit[stat_key] if stat_key else 0

    def get_outfit_efficiency(outfit_id, stat_name):
        if outfit_id not in outfit_mods:
            return 0
        outfit = outfit_mods[outfit_id]
        total_bonus = outfit['s'] + outfit['p'] + outfit['a']
        if total_bonus == 0:
            return 0
        relevant_bonus = get_outfit_bonus_for_stat(outfit_id, stat_name)
        return relevant_bonus / total_bonus

    # PHASE 1: Deficit balancing
    print("\n" + "-"*60)
    print("OUTFIT ASSIGNMENT - PHASE 1: DEFICIT BALANCING")
    print("-"*60)

    for room_key, need_data in sorted_rooms:
        stat_needed = need_data['stat']
        deficit = need_data['deficit']
        dwellers = need_data['dwellers']

        if deficit <= 0:
            print(f"\n{room_key} is already balanced or overcapacity")
            continue

        print(f"\n{room_key} needs +{round(deficit, 1)} {stat_needed}")

        if not any_outfit_left():
            print(f"  No outfits remaining")
            continue

        relevant_outfits = [
            oid for oid in outfit_inventory
            if oid in outfit_mods and get_outfit_bonus_for_stat(oid, stat_needed) > 0 and outfit_available(oid)
        ]

        if not relevant_outfits:
            print(f"  No outfits available with {stat_needed} bonus")
            continue

        best_outfits = sorted(
            relevant_outfits,
            key=lambda oid: (get_outfit_efficiency(oid, stat_needed), get_outfit_bonus_for_stat(oid, stat_needed)),
            reverse=True
        )

        dwellers_sorted = sorted(dwellers, key=lambda d: dweller_stats_with_outfits.get(d, {}).get(stat_needed, 0))

        for dweller_id in dwellers_sorted:
            if not best_outfits:
                break
            if dweller_id in outfit_assignments:
                continue

            outfit_id = best_outfits.pop(0)
            outfit_used[outfit_id] += 1
            outfit_assignments[dweller_id] = outfit_id
            outfit = outfit_mods[outfit_id]

            # Apply outfit bonuses
            dweller_stats_with_outfits[dweller_id]['Strength'] += outfit['s']
            dweller_stats_with_outfits[dweller_id]['Perception'] += outfit['p']
            dweller_stats_with_outfits[dweller_id]['Agility'] += outfit['a']

            bonus = get_outfit_bonus_for_stat(outfit_id, stat_needed)
            efficiency = round(get_outfit_efficiency(outfit_id, stat_needed) * 100, 1)
            print(f"  ✓ Assigned {outfit['name']} to Dweller {dweller_id} (+{bonus} {stat_needed}, {efficiency}% efficient)")

            deficit -= bonus
            if deficit <= 0:
                print(f"  ✓ Room balanced!")
                break

    # PHASE 2: High-value rooms
    if any_outfit_left():
        print("\n" + "-"*60)
        print("OUTFIT ASSIGNMENT - PHASE 2: HIGH-VALUE ROOMS")
        print("-"*60)
        
        remaining_count = sum(outfit_inventory[oid] - outfit_used.get(oid, 0) for oid in outfit_inventory)
        print(f"\n{remaining_count} outfits remaining")

        production_rooms = [(room_key, need_data) for room_key, need_data in room_needs.items()]
        level_scores = {'lvl3': 3, 'lvl2': 2, 'lvl1': 1}
        size_scores = {'size9': 9, 'size6': 6, 'size3': 3}
        production_rooms.sort(
            key=lambda x: (level_scores.get(x[0][1], 1) ** 2) * size_scores.get(x[0][2], 1),
            reverse=True
        )

        for room_key, need_data in production_rooms:
            if not any_outfit_left():
                break

            stat_needed = need_data['stat']
            dwellers = need_data['dwellers']
            unequipped_dwellers = [d for d in dwellers if d not in outfit_assignments]

            if not unequipped_dwellers:
                continue

            print(f"\nAssigning to {room_key}:")

            unequipped_dwellers.sort(key=lambda d: dweller_stats_with_outfits.get(d, {}).get(stat_needed, 0))

            relevant_outfits = [
                oid for oid in outfit_inventory
                if oid in outfit_mods and get_outfit_bonus_for_stat(oid, stat_needed) > 0 and outfit_available(oid)
            ]

            if not relevant_outfits:
                continue

            relevant_outfits.sort(key=lambda oid: get_outfit_bonus_for_stat(oid, stat_needed), reverse=True)

            for dweller_id in unequipped_dwellers:
                if not relevant_outfits:
                    break

                outfit_id = relevant_outfits.pop(0)
                outfit_used[outfit_id] += 1
                outfit_assignments[dweller_id] = outfit_id
                outfit = outfit_mods[outfit_id]

                dweller_stats_with_outfits[dweller_id]['Strength'] += outfit['s']
                dweller_stats_with_outfits[dweller_id]['Perception'] += outfit['p']
                dweller_stats_with_outfits[dweller_id]['Agility'] += outfit['a']

                bonus = get_outfit_bonus_for_stat(outfit_id, stat_needed)
                print(f"  ✓ Assigned {outfit['name']} to Dweller {dweller_id} (+{bonus} {stat_needed})")

    # Recalculate with outfits
    mean_finder_with_outfits = recalc_mean_finder(dweller_stats_with_outfits, sortedL)
    
    print("\n" + "="*60)
    print("PRODUCTION TIMES WITH OUTFITS")
    print("="*60)

    for room_key, t in mean_finder_with_outfits.items():
        if room_key[0] in TRAINING_ROOMS:
            continue
        old_time = after_balancing_times.get(room_key, 0)
        improvement = old_time - t
        print(f"{room_key} -> {t}s (was {old_time}s, improved by {round(improvement, 1)}s)")

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

    # FIX 4: Correct outfit assignment summary
    print(f"\n{'='*60}")
    print("OUTFIT ASSIGNMENT SUMMARY")
    print(f"{'='*60}")

    new_assignments = {k: v for k, v in outfit_assignments.items() if k not in existing_outfit_assignments}
    kept_existing = {k: v for k, v in outfit_assignments.items() if k in existing_outfit_assignments}
    
    print(f"Total outfits assigned: {len(outfit_assignments)}")
    print(f"  - Pre-existing (kept): {len(kept_existing)}")
    print(f"  - Newly assigned: {len(new_assignments)}")
    print(f"  - Relocated: {len(outfits_to_relocate)}")

    remaining = sum(outfit_inventory[oid] - outfit_used.get(oid, 0) for oid in outfit_inventory)
    print(f"Remaining unassigned outfits: {remaining}")

    # Plotting
    exclude = {"Gym", "Armory", "Dojo"}
    rooms = [r for r in list(before_balancing_times.keys()) if r[0] not in exclude]

    initial = [initial_mean_finder.get(r, np.nan) for r in rooms]
    before = [before_balancing_times.get(r, np.nan) for r in rooms]
    after = [after_balancing_times.get(r, np.nan) for r in rooms]
    with_outfits = [mean_finder_with_outfits.get(r, np.nan) for r in rooms]

    x = np.arange(len(rooms))
    width = 0.2  

    plt.figure(figsize=(14, 7))  
    plt.bar(x - 1.5*width, initial, width=width, label="Initial", color='#ff6b6b')
    plt.bar(x - 0.5*width, before, width=width, label="Before Balancing", color='#feca57')
    plt.bar(x + 0.5*width, after, width=width, label="After Balancing", color='#48dbfb')
    plt.bar(x + 1.5*width, with_outfits, width=width, label="With Outfits", color='#1dd1a1')

    plt.xticks(ticks=x, labels=[f"{r[0]}-{r[1]}-{r[2]}-{r[3]}" for r in rooms], rotation=45, ha="right")
    plt.ylabel("Production Time (s)")
    plt.title("Room Production Times: Initial → Balanced → Optimized with Outfits")
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    plot_filename = f"vault_production_{timestamp}.png"
    plt.savefig(plot_filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nPlot saved as: {plot_filename}")

    # Save optimization results to JSON
    optimization_results = {
        'timestamp': datetime.now().isoformat(),
        'vault_name': vault_name,
        'dweller_assignments': [],
        'room_assignments': {},
        'performance': {}
    }
    
    for dweller in dwellers_list:
        dweller_id = str(dweller.get('serializeId'))
        first_name = dweller.get('name', '')
        last_name = dweller.get('lastName', '')
        full_name = f"{first_name} {last_name}".strip()
        
        assigned_room = None
        for room_key, dwellers in sortedL.items():
            if dweller_id in dwellers:
                assigned_room = room_key
                break
        
        if assigned_room:
            room_type, stat, size = parse_room(assigned_room)
            assigned_room_info = {
                'room_type': assigned_room[0],
                'room_level': assigned_room[1],
                'room_size': assigned_room[2],
                'room_number': assigned_room[3],
            }

            previous_room_info = None
            for room_key, dwellers in initial_rooms.items():
                if dweller_id in dwellers:
                    previous_room_info = {
                        'room_type': room_key[0],
                        'room_level': room_key[1],
                        'room_size': room_key[2],
                        'room_number': room_key[3],
                    }
                    break

            moved_room_info = None
            if previous_room_info:
                prev_room_tuple = (
                    previous_room_info['room_type'],
                    previous_room_info['room_level'],
                    previous_room_info['room_size'],
                    previous_room_info['room_number'],
                )
                assigned_room_tuple = tuple(assigned_room[:4])

                if assigned_room_tuple != prev_room_tuple:
                    moved_room_info = {
                        'from': f"{prev_room_tuple[0]}_{prev_room_tuple[1]}_{prev_room_tuple[2]}_{prev_room_tuple[3]}",
                        'to': f"{assigned_room_tuple[0]}_{assigned_room_tuple[1]}_{assigned_room_tuple[2]}_{assigned_room_tuple[3]}",
                    }

            dweller_entry = {
                'id': dweller_id,
                'name': full_name if full_name else f"Dweller {dweller_id}",
                'assigned_room': assigned_room_info,
                'previous_room': previous_room_info,
                'primary_stat': stat,
                'stat_value': working_stats.get(dweller_id, {}).get(stat, 0),
                'dweller_moved': moved_room_info
            }

            # Add outfit info if assigned
            if dweller_id in outfit_assignments:
                outfit_id = outfit_assignments[dweller_id]
                outfit = outfit_mods[outfit_id]
                dweller_entry['outfit'] = {
                    'outfit_id': outfit_id,
                    'outfit_name': outfit.get('name', 'Unknown'),
                    'strength_bonus': outfit.get('s', 0),
                    'perception_bonus': outfit.get('p', 0),
                    'agility_bonus': outfit.get('a', 0),
                }

            optimization_results['dweller_assignments'].append(dweller_entry)

    # Save room assignments
    for room_key, dwellers in sortedL.items():
        room_id = f"{room_key[0]}_{room_key[1]}_{room_key[2]}_{room_key[3]}"
        dweller_list = []
        for dweller_id in dwellers:
            dweller_info = next((d for d in optimization_results['dweller_assignments'] if d['id'] == dweller_id), {})
            dweller_list.append({
                'id': dweller_id,
                'name': dweller_info.get('name', f"Dweller {dweller_id}")
            })
        
        optimization_results['room_assignments'][room_id] = {
            'room_type': room_key[0],
            'level': room_key[1],
            'size': room_key[2],
            'number': room_key[3],
            'dwellers': dweller_list,
            'initial_time': initial_mean_finder.get(room_key),
            'before_balance_time': before_balancing_times.get(room_key),
            'after_balance_time': after_balancing_times.get(room_key),
            'production_time': mean_finder_with_outfits.get(room_key)
        }
    
    optimization_results['performance'] = {
        'initial_avg': calculate_overall_average(initial_mean_finder),
        'before_balance_avg': calculate_overall_average(before_balancing_times),
        'after_balance_avg': calculate_overall_average(after_balancing_times),
        'with_outfits_avg': calculate_overall_average(mean_finder_with_outfits),
        'power_avg': round(geo_mean_new, 2) if geo_mean_new else None,
        'water_avg': round(wap_mean_new, 2) if wap_mean_new else None,
        'food_avg': round(caf_mean_new, 2) if caf_mean_new else None
    }
    
    results_file = f"{vault_name}_optimization_results.json"
    with open(results_file, 'w') as f:
        json.dump(optimization_results, f, indent=2)
    
    print(f"✓ Optimization results saved to {results_file}")
    
    from VaultPerformanceTracker import VaultPerformanceTracker
    tracker = VaultPerformanceTracker(vault_name)
    tracker.add_cycle_data(
        initial_avg=optimization_results['performance']['initial_avg'], 
        before_balance_avg=optimization_results['performance']['before_balance_avg'],
        after_balance_avg=optimization_results['performance']['after_balance_avg'],
        with_outfits_avg=optimization_results['performance']['with_outfits_avg']
    )

    conn.close()
    return results_file
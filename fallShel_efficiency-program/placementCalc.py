from asyncio.windows_events import NULL
from collections import defaultdict
import os
from statistics import median_grouped
import time
import json
import sqlite3
from matplotlib import pyplot as plt
import numpy as np
from datetime import datetime
from outfit_manager import OutfitDatabaseManager


class SwapLogger:
    def __init__(self, vault_happiness):
        self.vault_happiness = vault_happiness
        self.swap_history = []
        self.swap_count = 0
        
    def log_swap(self, dweller1_id, dweller2_id, room1_key, room2_key, 
                 before_times, after_times, dweller_stats, reason=""):
        self.swap_count += 1
        
        swap_record = {
            'swap_number': self.swap_count,
            'dweller1': dweller1_id,
            'dweller2': dweller2_id,
            'room1': self._format_room(room1_key),
            'room2': self._format_room(room2_key),
            'reason': reason,
            'room1_time_before': before_times.get(room1_key),
            'room1_time_after': after_times.get(room1_key),
            'room2_time_before': before_times.get(room2_key),
            'room2_time_after': after_times.get(room2_key),
            'improvement': self._calculate_improvement(before_times, after_times, room1_key, room2_key)
        }
        
        self.swap_history.append(swap_record)
        self._print_swap_details(swap_record, dweller_stats, room1_key, room2_key)
        
    def _format_room(self, room_key):
        return f"{room_key[0]}_{room_key[1]}_{room_key[2]}_{room_key[3]}"
    
    def _calculate_improvement(self, before_times, after_times, room1_key, room2_key):
        before_total = (before_times.get(room1_key, 0) + before_times.get(room2_key, 0))
        after_total = (after_times.get(room1_key, 0) + after_times.get(room2_key, 0))
        return round(before_total - after_total, 2)
    
    def _print_swap_details(self, record, dweller_stats, room1_key, room2_key):
        print(f"\n{'='*80}")
        print(f"SWAP #{record['swap_number']}: {record['reason']}")
        print(f"{'='*80}")
        
        # Get room stats needed
        _, stat1, _ = self._parse_room(room1_key)
        _, stat2, _ = self._parse_room(room2_key)
        
        # Dweller stats
        d1_stats = dweller_stats.get(record['dweller1'], {})
        d2_stats = dweller_stats.get(record['dweller2'], {})
        
        print(f"\nDweller Movement:")
        print(f"  Dweller {record['dweller1']} ({record['room1']} → {record['room2']})")
        print(f"    Stats: S:{d1_stats.get('Strength', 0)} P:{d1_stats.get('Perception', 0)} "
              f"E:{d1_stats.get('Endurance', 0)} C:{d1_stats.get('Charisma', 0)} "
              f"I:{d1_stats.get('Intelligence', 0)} A:{d1_stats.get('Agility', 0)} L:{d1_stats.get('Luck', 0)}")
        print(f"    Relevant stat for new room ({stat2}): {d1_stats.get(stat2, 0)}")
        
        print(f"\n  Dweller {record['dweller2']} ({record['room2']} → {record['room1']})")
        print(f"    Stats: S:{d2_stats.get('Strength', 0)} P:{d2_stats.get('Perception', 0)} "
              f"E:{d2_stats.get('Endurance', 0)} C:{d2_stats.get('Charisma', 0)} "
              f"I:{d2_stats.get('Intelligence', 0)} A:{d2_stats.get('Agility', 0)} L:{d2_stats.get('Luck', 0)}")
        print(f"    Relevant stat for new room ({stat1}): {d2_stats.get(stat1, 0)}")
        
        print(f"\nRoom Performance Changes:")
        print(f"  {record['room1']}:")
        print(f"    Before: {record['room1_time_before']}s → After: {record['room1_time_after']}s "
              f"(Δ {round(record['room1_time_before'] - record['room1_time_after'], 2)}s)")
        print(f"  {record['room2']}:")
        print(f"    Before: {record['room2_time_before']}s → After: {record['room2_time_after']}s "
              f"(Δ {round(record['room2_time_before'] - record['room2_time_after'], 2)}s)")
        
        print(f"\nOverall Improvement: {record['improvement']}s")
        
    def _parse_room(self, room_key):
        ROOM_STAT_MAP = {
            "Geothermal": "Strength",
            "Energy2": "Strength",
            "WaterPlant": "Perception",
            "Water2": "Perception",
            "Cafeteria": "Agility",
            "Hydroponic": "Agility",
            "MedBay": "Intelligence",
            "ScienceLab": "Intelligence",
            "NukaCola": "Perception+Agility"  
        }
        
        code = room_key[0]
        size = room_key[2]
        stat = ROOM_STAT_MAP.get(code)
        
        ROOM_CODE_MAP = {
            "Geothermal": "Power",
            "Energy2": "Power2",
            "WaterPlant": "Water",
            "Water2": "Water2",
            "Cafeteria": "Food",
            "Hydroponic": "Food2",
            "MedBay": "Medbay",
            "ScienceLab": "Medbay",
            "NukaCola": "NukaCola"
        }
        
        room_type = ROOM_CODE_MAP.get(code)
        return room_type, stat, size
    
    def print_summary(self):
        print(f"\n{'='*80}")
        print(f"SWAP SUMMARY - Total Swaps: {self.swap_count}")
        print(f"{'='*80}")
        
        total_improvement = sum(s['improvement'] for s in self.swap_history)
        print(f"\nTotal Time Improvement: {round(total_improvement, 2)}s")
        
        if self.swap_history:
            print(f"\nBest Single Swap: Swap #{max(self.swap_history, key=lambda s: s['improvement'])['swap_number']} "
                  f"({max(s['improvement'] for s in self.swap_history)}s improvement)")
            print(f"Worst Single Swap: Swap #{min(self.swap_history, key=lambda s: s['improvement'])['swap_number']} "
                  f"({min(s['improvement'] for s in self.swap_history)}s improvement)")


class BalancingConfig: 
    def __init__(self, optimizer_params = None):
        # Default priority: Intelligence (Medbay) > Others
        self.room_priorities = {
            'Medbay': 1,
            'Power': 2,
            'Power2': 2,
            'Water': 3,
            'Water2': 3,
            'Food': 4,
            'Food2': 4
        }
        
        # Apply optimizer parameters if provided
        if optimizer_params:
            self.balance_threshold = optimizer_params.get('BALANCE_THRESHOLD', 5.0)
            self.max_passes = optimizer_params.get('MAX_PASSES', 10)
            self.enable_cross_stat_balancing = optimizer_params.get('ENABLE_CROSS_STAT_BALANCING', True)
            self.outfit_strategy = optimizer_params.get('OUTFIT_STRATEGY', 'deficit_first')
            self.reference_baseline = optimizer_params.get('REFERENCE_BASELINE', 'auto')
            
            # Update room priorities from optimizer
            if 'ROOM_PRIORITIES' in optimizer_params and optimizer_params['ROOM_PRIORITIES']:
                custom_priorities = optimizer_params['ROOM_PRIORITIES']
                for room_type, priority in custom_priorities.items():
                    self.room_priorities[room_type] = priority
                    if room_type in ['Power', 'Water', 'Food']:
                        self.room_priorities[f"{room_type}2"] = priority
        else:
            self.balance_threshold = 5.0
            self.max_passes = 10
            self.enable_cross_stat_balancing = True
            self.outfit_strategy = 'deficit_first'
            self.reference_baseline = 'auto'
        
    def set_priorities(self, priorities_dict):

        self.room_priorities.update(priorities_dict)
        
    def get_priority(self, room_type):
        """Get priority for a room type"""
        return self.room_priorities.get(room_type, 999)
    
    def get_sorted_room_types(self):
        """Get room types sorted by priority"""
        return sorted(self.room_priorities.keys(), key=lambda rt: self.room_priorities[rt])


def run(json_path, outfitlist, vault_name, optimizer_params=None, balancing_config=None):
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
    
    # ===== OUTFIT DATABASE CHECK =====
    print_section("OUTFIT DATABASE CHECK")
    outfit_manager = OutfitDatabaseManager()
    
    # Check for missing outfits
    missing_outfits = outfit_manager.check_missing_outfits(outfitlist)
    
    if missing_outfits:
        print(f"⚠️  WARNING: Found {len(missing_outfits)} outfit(s) missing from database:")
        for outfit_id in missing_outfits:
            print(f"   - {outfit_id}")
        print("\n❌ ERROR: Cannot continue optimization without complete outfit data.")
        print("   The GUI will prompt you to enter missing outfit information.")
        print("   Please complete the outfit entry dialogs to continue.\n")
        
        return None
    else:
        print(f"✓ All {len(outfitlist)} outfits found in database")
        print("✓ Outfit check passed - continuing with optimization\n")
    
    # ===== INITIALIZE BALANCING CONFIG =====
    if balancing_config is None:
        balancing_config = BalancingConfig(optimizer_params)
    
    # ===== ADAPTIVE PARAMETERS =====
    if optimizer_params:
        balancing_config.balance_threshold = optimizer_params.get('BALANCE_THRESHOLD', 5.0)
        balancing_config.max_passes = optimizer_params.get('MAX_PASSES', 10)
        SWAP_AGGRESSIVENESS = optimizer_params.get('SWAP_AGGRESSIVENESS', 1.0)
        MIN_STAT_THRESHOLD = optimizer_params.get('MIN_STAT_THRESHOLD', 5)
    else:
        SWAP_AGGRESSIVENESS = 1.0
        MIN_STAT_THRESHOLD = 5

    OUTFIT_STRATEGY = balancing_config.outfit_strategy

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
        "Hydroponic": ("Food2", "Agility"),
        "MedBay": ("Medbay", "Intelligence"),
        "ScienceLab": ("Medbay", "Intelligence"),
        "NukaCola": ("NukaCola", ("Perception", "Agility"))  
    }

    ROOM_STAT_MAP = {
        "Geothermal": "Strength",
        "Energy2": "Strength",
        "WaterPlant": "Perception",
        "Water2": "Perception",
        "Cafeteria": "Agility",
        "Hydroponic": "Agility",
        "MedBay": "Intelligence",
        "ScienceLab": "Intelligence",
        "NukaCola": ("Perception", "Agility")
    }

    ROOM_GROUPS = {
        "Power": ("Geothermal", "Energy2"),
        "Water": ("WaterPlant", "Water2", "NukaCola"),  
        "Food": ("Cafeteria", "Hydroponic", "NukaCola"),  
        "Medbay": ("MedBay", "ScienceLab")
    }

    BASE_POOL = {
        "Power": 1320,
        "Food": 960,
        "Water": 960,
        "Power2": 1800,
        "Food2": 1200,
        "Water2": 1200,
        "Medbay": 2400,
        "NukaCola": 1200 
    }

    SIZE_MULTIPLIER = {"size3": 1, "size6": 2, "size9": 3}
    ROOM_CAPACITY = {"size3": 2, "size6": 4, "size9": 6}

    # --- Storage ---------------------------------------------------------------
    initial_rooms = {}
    _room_counts = defaultdict(int)
    Roomtables =  ["ConsumableRoom", "CraftingRoom", "Non_ProductionRoom", "ProductionRoom", "TrainingRoom" ]

    # --- Load ALL rooms for tracking (previous room assignments) ---------------
    all_rooms = []
    exclude = ["FakeWasteland","Elevator"]
    for t in Roomtables:
        cursor.execute(
            f"SELECT dweller_id, RoomName, Row, Column, RoomLevel, MergeLevel FROM {t} WHERE RoomName NOT IN {tuple(exclude)}",
        )
        all_rooms.extend(cursor.fetchall())
    
    # --- Load ONLY production rooms for balancing ------------------------------
    cursor.execute(
        "SELECT dweller_id, RoomName, Row, Column, RoomLevel, MergeLevel FROM ProductionRoom",
    )
    production_rooms = cursor.fetchall()

    def _lvl_str(room_level: int) -> str:
        return f"lvl{room_level if room_level in (1, 2, 3) else None}"

    def _size_str(merge_level: int) -> str:
        if merge_level == 1:
            return "size3"
        if merge_level == 2:
            return "size6"
        return "size9"

    # Build initial_rooms from ALL rooms (for tracking previous assignments)
    for dweller_ids, room_name, row, column, room_l, merge_l in all_rooms:
        if room_name in ROOM_STAT_MAP:
            dwellers = [x.strip() for x in str(dweller_ids).split(",") if x.strip()]

            base_key = (room_name, _lvl_str(room_l), _size_str(merge_l))
            _room_counts[base_key] += 1
            room_number = str(_room_counts[base_key])
            room_key = (base_key[0], base_key[1], base_key[2], room_number)
            initial_rooms[room_key] = dwellers
            
        else:
            dwellers = [x.strip() for x in str(dweller_ids).split(",") if x.strip()]
            base_key = (room_name, _lvl_str(room_l), _size_str(merge_l))
            _room_counts[base_key] += 1
            room_number = str(_room_counts[base_key])
            room_key = (base_key[0], base_key[1], base_key[2], room_number)
            initial_rooms[room_key] = dwellers
    
    print_section("INITIAL ROOMS AND ASSIGNED DWELLERS")
    for key, dwellers in initial_rooms.items():
        
        print(f" - {key} -> Dwellers: {', '.join(dwellers)}")

    # --- Parse vault_map.txt into room lists -----------------------------------
    geothermal = []
    waterPlant = []
    cafeteria = []
    meds = []
    gym = []
    armory = []
    dojo = []
    classroom = []

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
                    if "NukaCola" in room:
                        code = "NukaCola"
                    elif "Energy2" in room:
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
                    elif "MedBay" in room:
                        code = "MedBay"
                    elif "ScienceLab" in room:
                        code = "ScienceLab"
                    elif "Gym" in room:
                        code = "Gym"
                    elif "Armory" in room:
                        code = "Armory"
                    elif "Dojo" in room:
                        code = "Dojo"
                    elif "Classroom" in room:
                        code = "Classroom"

                    if not code:
                        continue

                    room_tuple = (code, f"lvl{lvl}", size_s, "1")

                    if code in ("Energy2", "Geothermal"):
                        geothermal.append(room_tuple)
                    elif code in ("WaterPlant", "Water2", "NukaCola"):
                        waterPlant.append(room_tuple)
                    elif code in ("Cafeteria", "Hydroponic"):
                        cafeteria.append(room_tuple)
                    elif code in ("MedBay", "ScienceLab"):
                        meds.append(room_tuple)
                    elif code == "Gym":
                        gym.append(room_tuple)
                    elif code == "Armory":
                        armory.append(room_tuple)
                    elif code == "Dojo":
                        dojo.append(room_tuple)
                    elif code == "Classroom":
                        classroom.append(room_tuple)
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

    RoomLists = [compact_room_list(geothermal), compact_room_list(waterPlant), 
                 compact_room_list(cafeteria), compact_room_list(meds)]

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
    meds = number_duplicates(RoomLists[3])

    total_rooms = len(geothermal) + len(waterPlant) + len(cafeteria) + len(meds)
    is_small_vault = total_rooms < 10

    if is_small_vault:
        print("\n🏠 Small vault detected - using conservative optimization")
        balancing_config.balance_threshold = 10.0
        balancing_config.max_passes = 5
    
    # --- Read ALL dweller stats and build complete lookup ----------------------
    Stats = {}
    dweller_stats = {}
    dweller_stats_initial = {}
    numDwellers = 0
    total_happiness = 0

    # Define all possible stats
    ALL_STATS = ['Strength', 'Perception', 'Endurance', 'Charisma', 'Intelligence', 'Agility', 'Luck']

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

        # Build complete stat maps with ALL stats
        stat_map_initial = {}
        stat_map = {}
        
        for _dwid, statname, value, mod in allStats:
            stat_map_initial[statname] = value
            # For current working stats, include modifier if it exists
            stat_map[statname] = value + (mod if mod is not None else 0)
        
        # Ensure all stats exist (default to 0 if missing)
        for stat_name in ALL_STATS:
            if stat_name not in stat_map_initial:
                stat_map_initial[stat_name] = 0
            if stat_name not in stat_map:
                stat_map[stat_name] = 0
        
        dweller_stats[str(serialize_id)] = stat_map
        dweller_stats_initial[str(serialize_id)] = stat_map_initial
        

    vault_happiness = round(total_happiness / numDwellers) if numDwellers > 0 else 0
    print(f"\nVault Average Happiness: {vault_happiness}%\n")

    # --- Load existing outfit assignments and apply bonuses to initial stats ---
    print_section("LOADING EXISTING OUTFIT ASSIGNMENTS")
    
    existing_outfit_assignments = {}
    cursor.execute("SELECT dweller_id, Outfit FROM dwellers WHERE Outfit IS NOT NULL AND outfit != ''")
    existing_outfits = cursor.fetchall()

    # Load outfit data
    outfit_mods = {}
    cursor.execute("SELECT Name, `Item ID`, S, P, A, I, E, C, L, Sex FROM Outfit")
    all_outfits = cursor.fetchall()
    
    for name, item_id, s_mod, p_mod, a_mod, i_mod, e_mod, c_mod, l_mod, sex in all_outfits:
        if name == "Jumpsuit":
            continue
        outfit_mods[item_id] = {
            'name': name,
            's': s_mod if s_mod is not None else 0,
            'p': p_mod if p_mod is not None else 0,
            'a': a_mod if a_mod is not None else 0,
            'i': i_mod if i_mod is not None else 0,
            'e': e_mod if e_mod is not None else 0,
            'c': c_mod if c_mod is not None else 0,
            'l': l_mod if l_mod is not None else 0,
            'sex': sex
        }

    print(f"Found {len(existing_outfits)} existing outfit assignments")
    
    # Apply existing outfit bonuses to initial stats
    for dweller_id, outfit_id in existing_outfits:
        dweller_id_str = str(dweller_id)
        existing_outfit_assignments[dweller_id_str] = outfit_id
        
        if outfit_id in outfit_mods:
            outfit = outfit_mods[outfit_id]
            # Apply to initial stats
            dweller_stats_initial[dweller_id_str]['Strength'] += outfit['s']
            dweller_stats_initial[dweller_id_str]['Perception'] += outfit['p']
            dweller_stats_initial[dweller_id_str]['Agility'] += outfit['a']
            dweller_stats_initial[dweller_id_str]['Intelligence'] += outfit['i']
            dweller_stats_initial[dweller_id_str]['Endurance'] += outfit['e']
            dweller_stats_initial[dweller_id_str]['Charisma'] += outfit['c']
            dweller_stats_initial[dweller_id_str]['Luck'] += outfit['l']
            
            print(f"  Dweller {dweller_id}: {outfit['name']} (S+{outfit['s']} P+{outfit['p']} "
                  f"E+{outfit['e']} C+{outfit['c']} I+{outfit['i']} A+{outfit['a']} L+{outfit['l']})")

    # --- Build best/second/worst lists efficiently -----------------------------
    bestGeo = []
    bestWaP = []
    bestCaf = []
    bestMed = []
    secbestGeo = []
    secbestWaP = []
    secbestCaf = []
    secbestMed = []
    worstGeo = []
    worstWaP = []
    worstCaf = []
    worstMed = []

    for serialize_id, stats in dweller_stats_initial.items():
        values = {k: v for k, v in stats.items() if k in ("Strength", "Perception", "Agility", "Intelligence")}
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
        elif highest_stat == "Intelligence":
            bestMed.append(f"{serialize_id} - {highest_val}")

        if second_stat == "Strength":
            secbestGeo.append(f"{serialize_id} - {second_val}")
        elif second_stat == "Perception":
            secbestWaP.append(f"{serialize_id} - {second_val}")
        elif second_stat == "Agility":
            secbestCaf.append(f"{serialize_id} - {second_val}")
        elif second_stat == "Intelligence":
            secbestMed.append(f"{serialize_id} - {second_val}")

        if lowest_stat == "Strength":
            worstGeo.append(f"{serialize_id} - {lowest_val}")
        elif lowest_stat == "Perception":
            worstWaP.append(f"{serialize_id} - {lowest_val}")
        elif lowest_stat == "Agility":
            worstCaf.append(f"{serialize_id} - {lowest_val}")
        elif lowest_stat == "Intelligence":
            worstMed.append(f"{serialize_id} - {lowest_val}")

    # sort lists
    bestGeo.sort(key=lambda s: int(s.split(" - ")[1]), reverse=True)
    bestWaP.sort(key=lambda s: int(s.split(" - ")[1]), reverse=True)
    bestCaf.sort(key=lambda s: int(s.split(" - ")[1]), reverse=True)
    bestMed.sort(key=lambda s: int(s.split(" - ")[1]), reverse=True)
    secbestGeo.sort(key=lambda s: int(s.split(" - ")[1]))
    secbestWaP.sort(key=lambda s: int(s.split(" - ")[1]))
    secbestCaf.sort(key=lambda s: int(s.split(" - ")[1]))
    secbestMed.sort(key=lambda s: int(s.split(" - ")[1]))
    worstGeo.sort(key=lambda s: int(s.split(" - ")[1]))
    worstWaP.sort(key=lambda s: int(s.split(" - ")[1]))
    worstCaf.sort(key=lambda s: int(s.split(" - ")[1]))
    worstMed.sort(key=lambda s: int(s.split(" - ")[1]))

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

    # --- Assign dwellers to production rooms (using INITIAL stats with outfits) ---
    geo_dwellers = extract_ids(bestGeo)
    caf_dwellers = extract_ids(bestCaf)
    wap_dwellers = extract_ids(bestWaP)
    med_dwellers = extract_ids(bestMed)

    if MIN_STAT_THRESHOLD > 0:
        geo_dwellers = [d for d in geo_dwellers if dweller_stats_initial.get(d, {}).get('Strength', 0) >= MIN_STAT_THRESHOLD]
        wap_dwellers = [d for d in wap_dwellers if dweller_stats_initial.get(d, {}).get('Perception', 0) >= MIN_STAT_THRESHOLD]
        caf_dwellers = [d for d in caf_dwellers if dweller_stats_initial.get(d, {}).get('Agility', 0) >= MIN_STAT_THRESHOLD]
        med_dwellers = [d for d in med_dwellers if dweller_stats_initial.get(d, {}).get('Intelligence', 0) >= MIN_STAT_THRESHOLD]

    sec_geo_dwellers = extract_ids(secbestGeo)
    sec_caf_dwellers = extract_ids(secbestCaf)
    sec_wap_dwellers = extract_ids(secbestWaP)
    sec_med_dwellers = extract_ids(secbestMed)

    thi_geo_dwellers = extract_ids(worstGeo)
    thi_caf_dwellers = extract_ids(worstCaf)
    thi_wap_dwellers = extract_ids(worstWaP)
    thi_med_dwellers = extract_ids(worstMed)

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
    meds_sorted = sorted(meds, key=room_priority_score, reverse=True)

    print("\n🎯 ROOM ASSIGNMENT PRIORITY ORDER:")
    print(f"Power rooms: {[f'{r[0]} {r[1]} {r[2]}' for r in geothermal_sorted]}")
    print(f"Water rooms: {[f'{r[0]} {r[1]} {r[2]}' for r in waterPlant_sorted]}")
    print(f"Food rooms: {[f'{r[0]} {r[1]} {r[2]}' for r in cafeteria_sorted]}")
    print(f"Med rooms: {[f'{r[0]} {r[1]} {r[2]}' for r in meds_sorted]}\n")

    # Round 1
    assign_rooms(geothermal_sorted, geo_dwellers)
    assign_rooms(waterPlant_sorted, wap_dwellers)
    assign_rooms(cafeteria_sorted, caf_dwellers)
    assign_rooms(meds_sorted, med_dwellers)

    # Round 2
    secRdwellers = get_unassignedID(sec_geo_dwellers, sec_caf_dwellers, sec_wap_dwellers, sec_med_dwellers)
    get_unassigned_stat(secbestGeo, secRdwellers)
    get_unassigned_stat(secbestCaf, secRdwellers)
    get_unassigned_stat(secbestWaP, secRdwellers)
    get_unassigned_stat(secbestMed, secRdwellers)
    assign_rooms(geothermal, sec_geo_dwellers)
    assign_rooms(waterPlant, sec_wap_dwellers)
    assign_rooms(cafeteria, sec_caf_dwellers)
    assign_rooms(meds, sec_med_dwellers)

    # Round 3
    thiRdwellers = get_unassignedID(thi_geo_dwellers, thi_caf_dwellers, thi_wap_dwellers, thi_med_dwellers)
    get_unassigned_stat(worstGeo, thiRdwellers)
    get_unassigned_stat(worstCaf, thiRdwellers)
    get_unassigned_stat(worstWaP, thiRdwellers)
    get_unassigned_stat(worstMed, thiRdwellers)
    assign_rooms(geothermal, thi_geo_dwellers)
    assign_rooms(waterPlant, thi_wap_dwellers)
    assign_rooms(cafeteria, thi_caf_dwellers)
    assign_rooms(meds, thi_med_dwellers)

    leftOver = get_unassignedID(thi_geo_dwellers, thi_caf_dwellers, thi_wap_dwellers, thi_med_dwellers)

    print("")
    for room, dwellers in sortedL.items():
        print(f"Room: {room} -> Dwellers: {', '.join(dwellers)}")
    print("")

    # --- Training assignments ---------------------------------------------------
    get_unassigned_stat(worstGeo, leftOver)
    get_unassigned_stat(worstCaf, leftOver)
    get_unassigned_stat(worstWaP, leftOver)
    get_unassigned_stat(worstMed, leftOver)

    for lst in (worstGeo, worstCaf, worstWaP, worstMed):
        lst.sort(key=lambda x: int(x.split(" - ")[1]))

    assign_rooms(gym, extract_ids(worstGeo))
    assign_rooms(dojo, extract_ids(worstCaf))
    assign_rooms(armory, extract_ids(worstWaP))
    assign_rooms(classroom, extract_ids(worstMed))

    get_unassigned_stat(secbestGeo, leftOver)
    get_unassigned_stat(secbestCaf, leftOver)
    get_unassigned_stat(secbestWaP, leftOver)
    get_unassigned_stat(secbestMed, leftOver)

    for lst in (secbestGeo, secbestCaf, secbestWaP, secbestMed):
        lst.sort(key=lambda x: int(x.split(" - ")[1]))

    assign_rooms(gym, extract_ids(secbestGeo))
    assign_rooms(dojo, extract_ids(secbestCaf))
    assign_rooms(armory, extract_ids(secbestWaP))
    assign_rooms(classroom, extract_ids(secbestMed))

    get_unassigned_stat(bestGeo, leftOver)
    get_unassigned_stat(bestCaf, leftOver)
    get_unassigned_stat(bestWaP, leftOver)
    get_unassigned_stat(bestMed, leftOver)

    for lst in (bestGeo, bestCaf, bestWaP, bestMed):
        lst.sort(key=lambda x: int(x.split(" - ")[1]))

    assign_rooms(gym, extract_ids(bestGeo))
    assign_rooms(dojo, extract_ids(bestCaf))
    assign_rooms(armory, extract_ids(bestWaP))
    assign_rooms(classroom, extract_ids(bestMed))

    print("\nTraining Rooms:")
    for room, dwellers in sortedL.items():
        if room[0] in ("Gym", "Armory", "Dojo", "Classroom"):
            print(f"Room: {room} -> Dwellers: {', '.join(dwellers)}")
    print("")

    allDwellerIDs = {str(d["serializeId"]) for d in dwellers_list}
    assigned = set()
    for dwellers in sortedL.values():
        assigned.update(dwellers)
    finalRemaining = list(allDwellerIDs - assigned)

    print("\nFinal Unassigned Dwellers:")
    print(", ".join(finalRemaining))

    # --- Production time helpers (CORRECTED FORMULA) ----------------------------
    TRAINING_ROOMS = {"Armory", "Dojo", "Gym", "Classroom"}

    def parse_room(room_key):
        code = room_key[0]
        size = room_key[2]
        room_type, stat = ROOM_CODE_MAP.get(code, (None, None))
        # stat can be a string (single stat) or tuple (dual stats like NukaCola)
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

        pool = BASE_POOL[room_type] * SIZE_MULTIPLIER[size]
        
        # Handle dual-stat rooms (like NukaCola)
        if isinstance(stat, tuple):
            # For dual-stat rooms, use the average of both stats
            stat1, stat2 = stat
            total_stat = sum(
                (dweller_stats.get(d, {}).get(stat1, 0) + dweller_stats.get(d, {}).get(stat2, 0)) / 2
                for d in dwellers
            )
        else:
            # Single-stat rooms
            total_stat = sum(dweller_stats.get(d, {}).get(stat, 0) for d in dwellers)

        if total_stat == 0:
            return None

       
        rounded_percent = (happiness/100)
        production_time = pool / (total_stat * (1 + rounded_percent))

        return round(production_time, 1)

    def recalc_mean_finder(stats_dict, sortList, happiness_value):
        result = {}
        for room_key, dwellers in sortList.items():
            t = get_room_production_time(room_key, dwellers, stats_dict, happiness=happiness_value)
            if t:
                result[room_key] = t
        return result

    def calculate_overall_average(mean_map):
        times = [t for r, t in mean_map.items() if r[0] not in TRAINING_ROOMS]
        return round(sum(times) / len(times), 2) if times else 0

    def group_means(mean_map):
        geo = [t for r, t in mean_map.items() if r[0] in ("Geothermal", "Energy2")]
        wap = [t for r, t in mean_map.items() if r[0] in ("WaterPlant", "Water2", "NukaCola")]
        caf = [t for r, t in mean_map.items() if r[0] in ("Cafeteria", "Hydroponic", "NukaCola")]
        med = [t for r, t in mean_map.items() if r[0] in ("MedBay", "ScienceLab")]
        nuka = [t for r, t in mean_map.items() if r[0] == "NukaCola"]
        return (
            (sum(geo) / len(geo)) if geo else None,
            (sum(wap) / len(wap)) if wap else None,
            (sum(caf) / len(caf)) if caf else None,
            (sum(med) / len(med)) if med else None,
            (sum(nuka) / len(nuka)) if nuka else None,  # NukaCola separate average
        )

    # --- Calculate initial times (with existing outfits applied) ---------------
    happiness_decimal = vault_happiness / 100
    
    print("\nTIME BEFORE ANY CHANGES (INITIAL STATE - WITH EXISTING OUTFITS)")
    initial_mean_finder = recalc_mean_finder(dweller_stats_initial, initial_rooms, happiness_decimal)
    
    for room_key, t in initial_mean_finder.items():
        room_type, stat, size = parse_room(room_key)
        dwellers = initial_rooms[room_key]
        total_stat = sum(dweller_stats_initial.get(d, {}).get(stat, 0) for d in dwellers)
        print(f"{room_key} -> {t}s ({stat}:{total_stat})")

    print("\nTIME AFTER INITIAL ASSIGNMENT (BEFORE BALANCING - WITH EXISTING OUTFITS)")
    before_balancing_times = recalc_mean_finder(dweller_stats_initial, sortedL, happiness_decimal)
    
    for room_key, t in before_balancing_times.items():
        print(f"{room_key} -> {t} seconds")

    geo_mean, wap_mean, caf_mean, med_mean, nuka_mean = group_means(before_balancing_times)

    if geo_mean is not None:
        print(f"\nGeothermal Average Time: {round(geo_mean,1)} seconds")
    if wap_mean is not None:
        print(f"Water Plant Average Time: {round(wap_mean,1)} seconds")
    if caf_mean is not None:
        print(f"Cafeteria Average Time: {round(caf_mean,1)} seconds")
    if med_mean is not None:
        print(f"Medbay Average Time: {round(med_mean,1)} seconds")
    if nuka_mean is not None:
        print(f"NukaCola Average Time: {round(nuka_mean,1)} seconds")

    initial_overall_avg = calculate_overall_average(initial_mean_finder)
    before_balance_overall_avg = calculate_overall_average(before_balancing_times)

    print(f"\n{'='*60}")
    print("PERFORMANCE COMPARISON")
    print(f"{'='*60}")
    print(f"Initial Average Time: {initial_overall_avg}s")
    print(f"Before Balancing Average Time: {before_balance_overall_avg}s")


    working_stats = dweller_stats_initial.copy()
    outfit_owner_beforeswap = {}
    def get_outfit_bonus(dweller_id):
        outfit_id = existing_outfit_assignments.get(dweller_id)
        if outfit_id and outfit_id in outfit_mods:
            return outfit_mods[outfit_id]
        return None

    # Check user's reference baseline preference
    reference_baseline = balancing_config.reference_baseline
    
    if reference_baseline == 'before_balancing':
        print(f"\nℹ️  Reference Baseline Setting: BEFORE BALANCING (user-forced)")
        print(f"    Using BEFORE BALANCING state as baseline for balancing process")
        outfit_owner_beforeswap = {d: get_outfit_bonus(d) for dwellers in sortedL.values() for d in dwellers}
    elif reference_baseline == 'initial':
        print(f"\nℹ️  Reference Baseline Setting: INITIAL STATE (user-forced)")
        print(f"    Using INITIAL state as baseline for balancing process")
        sortedL.clear()
        for room_key, dwellers in initial_rooms.items():
            sortedL[room_key] = dwellers.copy()
            outfit_owner_beforeswap.update({d: get_outfit_bonus(d) for d in dwellers})
        print(f"    ✓ Balancing will optimize from initial state")
    else:
        print(f"\nℹ️ AUTO")
        if initial_overall_avg > 0 and initial_overall_avg < before_balance_overall_avg:
            print(f"    ⚠️  Initial assignment ({initial_overall_avg}s) is BETTER than before balancing ({before_balance_overall_avg}s)")
            print(f"    Using INITIAL state as baseline for balancing process")
            sortedL.clear()
            for room_key, dwellers in initial_rooms.items():
                sortedL[room_key] = dwellers.copy()
                outfit_owner_beforeswap.update({d: get_outfit_bonus(d) for d in dwellers})

            print(f"    ✓ Balancing will optimize from initial state")
        else:
            print(f"    ✓ Before balancing ({before_balance_overall_avg}s) is better than or equal to initial ({initial_overall_avg}s)")
            print(f"    Using BEFORE BALANCING state as baseline")
            outfit_owner_beforeswap = {d: get_outfit_bonus(d) for dwellers in sortedL.values() for d in dwellers}

    # --- ENHANCED CROSS-STAT BALANCING WITH DETAILED LOGGING -------------------
    print_section("CROSS-STAT BALANCING WITH PRIORITY-BASED OPTIMIZATION")
    
    swap_logger = SwapLogger(vault_happiness)
    
    print(f"Balancing Configuration:")
    print(f"  Balance Threshold: {balancing_config.balance_threshold}s")
    print(f"  Max Passes: {balancing_config.max_passes}")
    print(f"  Cross-Stat Balancing: {'Enabled' if balancing_config.enable_cross_stat_balancing else 'Disabled'}")
    print(f"  Reference Baseline: {balancing_config.reference_baseline}")
    print(f"\nRoom Type Priorities (lower = higher priority):")
    for room_type in balancing_config.get_sorted_room_types():
        priority = balancing_config.get_priority(room_type)
        print(f"  {room_type}: Priority {priority}")
        



    for pass_num in range(1, balancing_config.max_passes + 1):
        mean_finder = recalc_mean_finder(working_stats, sortedL, happiness_decimal)
        geo_mean, wap_mean, caf_mean, med_mean, nuka_mean = group_means(mean_finder)
        
        # Group means by room type
        group_targets = {
            'Power': geo_mean,
            'Power2': geo_mean,
            'Water': wap_mean,
            'Water2': wap_mean,
            'Food': caf_mean,
            'Food2': caf_mean,
            'Medbay': med_mean,
            'NukaCola': nuka_mean  # NukaCola uses its own average
        }

        if not mean_finder:
            break

        def is_balanced_local():
            for r, t in mean_finder.items():
                rtype, _, _ = parse_room(r)
                target = group_targets.get(rtype)
                if target is None or t is None:
                    continue
                if abs(t - target) > balancing_config.balance_threshold:
                    return False
            return True

        if is_balanced_local():
            print(f"\n✓ Balanced after {pass_num - 1} passes")
            break

        print(f"\n{'='*80}")
        print(f"BALANCE PASS {pass_num}")
        print(f"{'='*80}")

        swaps_this_pass = 0
        
        all_production_rooms = [(r, mean_finder[r]) for r in mean_finder 
                               if r[0] not in TRAINING_ROOMS]
        



        if balancing_config.enable_cross_stat_balancing:
            room_deviations = []
            for room_key, prod_time in all_production_rooms:
                rtype, stat, size = parse_room(room_key)
                target = group_targets.get(rtype)
                if target is None:
                    continue
                
                deviation = prod_time - target
                priority = balancing_config.get_priority(rtype)
                
                room_deviations.append({
                    'room': room_key,
                    'time': prod_time,
                    'target': target,
                    'deviation': deviation,
                    'priority': priority,
                    'type': rtype,
                    'stat': stat
                })
            

            room_deviations.sort(key=lambda x: (x['priority'], -abs(x['deviation'])))
            




            for room_data in room_deviations:
                if swaps_this_pass >= 20:  
                    break
                
                slow_room = room_data['room']
                slow_time = room_data['time']
                slow_stat = room_data['stat']
                slow_target = room_data['target']
                
                # Skip if already close to target
                if abs(slow_time - slow_target) <= balancing_config.balance_threshold:
                    continue
                
                # Find dweller in slow room with worst stat for that room
                if not sortedL.get(slow_room):
                    continue
                
                # Handle dual-stat rooms
                if isinstance(slow_stat, tuple):
                    # For dual-stat rooms, find dweller with worst average of both stats
                    stat1, stat2 = slow_stat
                    worst_in_slow = min(sortedL[slow_room], 
                                       key=lambda d: (working_stats.get(d, {}).get(stat1, 0) + 
                                                     working_stats.get(d, {}).get(stat2, 0)) / 2)
                    worst_stat_value = (working_stats.get(worst_in_slow, {}).get(stat1, 0) + 
                                       working_stats.get(worst_in_slow, {}).get(stat2, 0)) / 2
                else:
                    worst_in_slow = min(sortedL[slow_room], 
                                       key=lambda d: working_stats.get(d, {}).get(slow_stat, 0))
                    worst_stat_value = working_stats.get(worst_in_slow, {}).get(slow_stat, 0)
                
                best_swap = None
                best_improvement = 0
                
                for other_room, other_time in all_production_rooms:
                    if other_room == slow_room or not sortedL.get(other_room):
                        continue
                    
                    other_type, other_stat, other_size = parse_room(other_room)
                    other_target = group_targets.get(other_type)
                    
                    # Find dweller in other room who would be better in slow room
                    for other_dweller in sortedL[other_room]:
                        other_dweller_stats = working_stats.get(other_dweller, {})
                        
                        # Calculate stat values for comparison (handle dual-stat rooms)
                        if isinstance(slow_stat, tuple):
                            stat1, stat2 = slow_stat
                            other_in_slow_stat = (other_dweller_stats.get(stat1, 0) + 
                                                 other_dweller_stats.get(stat2, 0)) / 2
                        else:
                            other_in_slow_stat = other_dweller_stats.get(slow_stat, 0)
                        
                        if isinstance(other_stat, tuple):
                            stat1, stat2 = other_stat
                            worst_in_other_stat = (working_stats.get(worst_in_slow, {}).get(stat1, 0) + 
                                                  working_stats.get(worst_in_slow, {}).get(stat2, 0)) / 2
                        else:
                            worst_in_other_stat = working_stats.get(worst_in_slow, {}).get(other_stat, 0)
                        
                        if other_in_slow_stat <= worst_stat_value:
                            continue
                        
                        temp_slow = [d for d in sortedL[slow_room] if d != worst_in_slow]
                        temp_other = [d for d in sortedL[other_room] if d != other_dweller]

                        temp_slow.append(other_dweller)
                        temp_other.append(worst_in_slow)
                        
                        # Calculate new times
                        new_slow_time = get_room_production_time(slow_room, temp_slow, working_stats, happiness_decimal)
                        new_other_time = get_room_production_time(other_room, temp_other, working_stats, happiness_decimal)
                        
                        if new_slow_time is None or new_other_time is None:
                            continue
                        
                        # Calculate improvement
                        slow_improvement = slow_time - new_slow_time
                        other_change = new_other_time - other_time
                        
                        # Weighted improvement (prioritize slow room)
                        total_improvement = (slow_improvement * 1.5) - other_change
                        
                        # Only accept if net positive
                        if total_improvement > best_improvement:
                            best_improvement = total_improvement
                            best_swap = {
                                'other_room': other_room,
                                'other_dweller': other_dweller,
                                'new_slow_time': new_slow_time,
                                'new_other_time': new_other_time
                            }
                
                # Execute best swap if found
                if best_swap and best_improvement > 0.5:
                    other_room = best_swap['other_room']
                    other_dweller = best_swap['other_dweller']
                    
                    # Record before state
                    before_times = mean_finder.copy()
                    
                    # Execute swap
                    sortedL[slow_room].remove(worst_in_slow)
                    sortedL[other_room].remove(other_dweller)
                    sortedL[slow_room].append(other_dweller)
                    sortedL[other_room].append(worst_in_slow)
                    
                    # Recalculate times
                    mean_finder = recalc_mean_finder(working_stats, sortedL, happiness_decimal)
                    
                    # Log the swap
                    reason = f"Cross-stat optimization: Improving {room_data['type']} (Priority {room_data['priority']})"
                    swap_logger.log_swap(worst_in_slow, other_dweller, slow_room, other_room,
                                        before_times, mean_finder, working_stats, reason)
                    
                    swaps_this_pass += 1



        else:
            # SAME-STAT BALANCING ONLY (original logic)
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

                if time_diff < balancing_config.balance_threshold * 2:
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

                # Record before state
                before_times = mean_finder.copy()
                
                # Execute swap
                sortedL[strongest].remove(best_from_strong)
                sortedL[weakest].remove(worst_from_weak)
                sortedL[strongest].append(worst_from_weak)
                sortedL[weakest].append(best_from_strong)
                
                # Recalculate times
                mean_finder = recalc_mean_finder(working_stats, sortedL, happiness_decimal)
                
                # Log the swap
                reason = f"Same-stat balancing within {room_type}"
                swap_logger.log_swap(best_from_strong, worst_from_weak, strongest, weakest,
                                    before_times, mean_finder, working_stats, reason)
                
                swaps_this_pass += 1
        
        if swaps_this_pass == 0:
            print(f"\nNo beneficial swaps found in pass {pass_num} - stopping")
            break
        else:
            print(f"\nCompleted {swaps_this_pass} swap(s) in pass {pass_num}")



    # Print swap summary
    swap_logger.print_summary()

    # --- Final state after balancing ---
    print("")
    for room, dwellers in sortedL.items():
        print(f"Room: {room} -> Dwellers: {', '.join(dwellers)}")
    print("")

    after_balancing_times = recalc_mean_finder(working_stats, sortedL, happiness_decimal)

    print("\nFINAL TIMES AFTER BALANCING")
    for room_key, t in after_balancing_times.items():
        print(f"{room_key} -> {t} seconds")

    geo_mean, wap_mean, caf_mean, med_mean, nuka_mean = group_means(after_balancing_times)

    if geo_mean is not None:
        print(f"\nGeothermal Average Time: {round(geo_mean,1)} seconds")
    if wap_mean is not None:
        print(f"Water Plant Average Time: {round(wap_mean,1)} seconds")
    if caf_mean is not None:
        print(f"Cafeteria Average Time: {round(caf_mean,1)} seconds")
    if med_mean is not None:
        print(f"Medbay Average Time: {round(med_mean,1)} seconds")
    if nuka_mean is not None:
        print(f"NukaCola Average Time: {round(nuka_mean,1)} seconds")

    # --- OUTFIT OPTIMIZATION (based on after-balancing placement) ---------------
    print("\n" + "="*60)
    print("OUTFIT OPTIMIZATION")
    print("="*60)

    # Get outfit strategy from optimizer config
    outfit_strategy = balancing_config.outfit_strategy if hasattr(balancing_config, 'outfit_strategy') else 'deficit_first'
    print(f"Using strategy: {outfit_strategy}")

    # FIRST: Build complete map of who owned what outfit BEFORE any changes
    outfit_previous_owners_list = defaultdict(list)
    for dweller_id, outfit_id in existing_outfit_assignments.items():
        if outfit_id:
            outfit_previous_owners_list[outfit_id].append(dweller_id)

    print(f"\nTracked outfit ownership for {len(outfit_previous_owners_list)} outfit types before optimization")
    for outfit_id, owners in outfit_previous_owners_list.items():
        outfit_name = outfit_mods.get(outfit_id, {}).get('name', outfit_id)
        print(f"  {outfit_name}: {len(owners)} dweller(s)")

    # Start fresh for NEW outfit assignments
    outfit_assignments = {}
    outfit_stat_map = {'Strength': 's', 'Perception': 'p', 'Agility': 'a', 'Intelligence': 'i',
                        'Endurance': 'e', 'Charisma': 'c', 'Luck': 'l'}

    def get_dweller_gender(dweller_id):
        """Return 'M', 'F', or '' for the given dweller ID."""
        cursor.execute(
            "SELECT Gender FROM dwellers WHERE dweller_id = ?", (dweller_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return ""
        return (row[0] or "").strip()

    # Validate existing outfits against NEW placement
    print("\n" + "-"*60)
    print("VALIDATING EXISTING OUTFIT ASSIGNMENTS AGAINST NEW PLACEMENT")
    print("-"*60)

    outfits_to_relocate = []

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
                outfit_assignments[dweller_id] = outfit_id
                print(f"✓ Dweller {dweller_id} in {room_type} room with {outfit['name']} (+{outfit[stat_key]} {stat})")
            else:
                print(f"⚠️  Dweller {dweller_id} in {room_type} room has MISPLACED {outfit['name']}")
                outfits_to_relocate.append((dweller_id, outfit_id))

    # Handle relocations FIRST, before applying outfit bonuses
    if outfits_to_relocate:
        print(f"\n⚠️  Found {len(outfits_to_relocate)} misplaced outfits - attempting to relocate...")

        # REMOVE MISPLACED OUTFITS FROM outfit_assignments FIRST
        for old_dweller_id, outfit_id in outfits_to_relocate:
            if old_dweller_id in outfit_assignments:
                del outfit_assignments[old_dweller_id]



        for old_dweller_id, outfit_id in outfits_to_relocate:
            outfit = outfit_mods[outfit_id]
            stat_bonuses = [('Strength', outfit['s']), ('Perception', outfit['p']), 
                          ('Agility', outfit['a']), ('Intelligence', outfit['i'])]
            best_stat = max(stat_bonuses, key=lambda x: x[1])
            best_stat_name, best_stat_value = best_stat
    
            if best_stat_value == 0:
                continue
    
            found_new_home = False
            for room_key, room_dwellers in sortedL.items():
                room_type, stat, size = parse_room(room_key)
                if room_key[0] in TRAINING_ROOMS:
                    continue
                if stat == best_stat_name:
                    for potential_dweller in room_dwellers:
                        if potential_dweller not in outfit_assignments and potential_dweller != old_dweller_id:
                            # Gender compatibility check
                            dweller_sex = get_dweller_gender(potential_dweller)
                            if not outfit_manager.is_outfit_compatible(dweller_sex, outfit_id):
                                continue
                            outfit_assignments[potential_dweller] = outfit_id
                            print(f"  ✓ Moved {outfit['name']} from Dweller {old_dweller_id} to Dweller {potential_dweller}")
                            found_new_home = True
                            break
                if found_new_home:
                    break
            if not found_new_home:
                print(f"  ⚠️  Could not relocate {outfit['name']} from Dweller {old_dweller_id}")
 
    dweller_stats_with_outfits = {k: v.copy() for k, v in working_stats.items()}
    
    for dweller_id, outfit_id in existing_outfit_assignments.items():
        if outfit_id in outfit_mods and dweller_id in dweller_stats_with_outfits:
            outfit = outfit_mods[outfit_id]
            dweller_stats_with_outfits[dweller_id]['Strength'] -= outfit['s']
            dweller_stats_with_outfits[dweller_id]['Perception'] -= outfit['p']
            dweller_stats_with_outfits[dweller_id]['Agility'] -= outfit['a']
            dweller_stats_with_outfits[dweller_id]['Intelligence'] -= outfit['i']
            dweller_stats_with_outfits[dweller_id]['Endurance'] -= outfit['e']
            dweller_stats_with_outfits[dweller_id]['Charisma'] -= outfit['c']
            dweller_stats_with_outfits[dweller_id]['Luck'] -= outfit['l']

    # Apply ALL outfit bonuses from outfit_assignments (includes existing, relocated, and new)
    for dweller_id, outfit_id in outfit_assignments.items():
        if outfit_id in outfit_mods:
            outfit = outfit_mods[outfit_id]
            dweller_stats_with_outfits[dweller_id]['Strength'] += outfit['s']
            dweller_stats_with_outfits[dweller_id]['Perception'] += outfit['p']
            dweller_stats_with_outfits[dweller_id]['Agility'] += outfit['a']
            dweller_stats_with_outfits[dweller_id]['Intelligence'] += outfit['i']
            dweller_stats_with_outfits[dweller_id]['Endurance'] += outfit['e']
            dweller_stats_with_outfits[dweller_id]['Charisma'] += outfit['c']
            dweller_stats_with_outfits[dweller_id]['Luck'] += outfit['l']


    # Calculate room needs based on after-balancing placement
    room_needs = {}
    current_times = recalc_mean_finder(dweller_stats_with_outfits, sortedL, happiness_decimal)

    # Recalculate group means
    geo_mean_curr, wap_mean_curr, caf_mean_curr, med_mean_curr, nuka_mean_curr = group_means(current_times)

    for room_key, prod_time in current_times.items():
        room_type, stat, size = parse_room(room_key)
        if room_type is None or room_key[0] in TRAINING_ROOMS:
            continue

        if room_type in ("Power", "Power2"):
            target = geo_mean_curr
        elif room_type in ("Water", "Water2"):
            target = wap_mean_curr
        elif room_type in ("Food", "Food2"):
            target = caf_mean_curr
        elif room_type == "Medbay":
            target = med_mean_curr
        elif room_type == "NukaCola":
            target = nuka_mean_curr
        else:
            continue

        if target is None:
            continue

        pool = BASE_POOL[room_type] * SIZE_MULTIPLIER[size]
        dwellers = sortedL[room_key]
        
        # Handle dual-stat rooms for current_total calculation
        if isinstance(stat, tuple):
            stat1, stat2 = stat
            current_total = sum(
                (dweller_stats_with_outfits.get(d, {}).get(stat1, 0) + 
                 dweller_stats_with_outfits.get(d, {}).get(stat2, 0)) / 2
                for d in dwellers
            )
        else:
            current_total = sum(dweller_stats_with_outfits.get(d, {}).get(stat, 0) for d in dwellers)
    
        happiness = (happiness_decimal/100)
        ideal_total = pool / (target * (1 + happiness))
        stat_deficit = ideal_total - current_total

        room_needs[room_key] = {
            'stat': stat,
            'deficit': stat_deficit,
            'current_time': prod_time,
            'target_time': target,
            'dwellers': dwellers,
            'size': size,
            'room_type': room_type
        }

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

    def get_outfit_total_bonus(outfit_id):
        if outfit_id not in outfit_mods:
            return 0
        outfit = outfit_mods[outfit_id]
        return outfit['s'] + outfit['p'] + outfit['a'] + outfit['i'] + outfit['e'] + outfit['c'] + outfit['l']

    def get_outfit_efficiency(outfit_id, stat_name):
        """Calculate how efficiently an outfit's total stats match the needed stat"""
        total = get_outfit_total_bonus(outfit_id)
        if total == 0:
            return 0
        relevant = get_outfit_bonus_for_stat(outfit_id, stat_name)
        return relevant / total

    def get_room_value_score(room_key):
        """Calculate room value based on level and size"""
        level_scores = {'lvl3': 3, 'lvl2': 2, 'lvl1': 1}
        size_scores = {'size9': 9, 'size6': 6, 'size3': 3}
        level_score = level_scores.get(room_key[1], 1)
        size_score = size_scores.get(room_key[2], 1)
        return (level_score ** 2) * size_score

    def get_room_priority(room_type):
        """Get priority for room type (lower = higher priority)"""
        return balancing_config.get_priority(room_type)

    # ============================================================================
    # STRATEGY FUNCTIONS
    # ============================================================================

    def sort_rooms_deficit_first(room_needs):
        """deficit_first: Prioritize rooms needing most help"""
        def sort_key(item):
            room_key, need_data = item
            room_type = need_data['room_type']
            priority = get_room_priority(room_type)
            deficit = need_data['deficit']
            # Primary: room priority, Secondary: deficit amount
            return (priority, -deficit)
    
        return sorted(room_needs.items(), key=sort_key)

    def sort_rooms_big_rooms_first(room_needs):
        """big_rooms_first: Prioritize high-level/merged rooms"""
        def sort_key(item):
            room_key, need_data = item
            room_type = need_data['room_type']
            priority = get_room_priority(room_type)
            value_score = get_room_value_score(room_key)
            # Primary: room priority, Secondary: room value (size * level)
            return (priority, -value_score)
    
        return sorted(room_needs.items(), key=sort_key)

    def sort_rooms_hybrid(room_needs):
        """hybrid: Balance between deficit and room size"""
        def sort_key(item):
            room_key, need_data = item
            room_type = need_data['room_type']
            priority = get_room_priority(room_type)
            deficit = need_data['deficit']
            value_score = get_room_value_score(room_key)
            # Normalize both scores and combine
            deficit_normalized = deficit / 10  # Rough normalization
            value_normalized = value_score / 27  # Max is 9*9=81, typical is ~27
            hybrid_score = (deficit_normalized * 0.6) + (value_normalized * 0.4)
            # Primary: room priority, Secondary: hybrid score
            return (priority, -hybrid_score)
    
        return sorted(room_needs.items(), key=sort_key)

    def sort_rooms_efficiency_first(room_needs):
        """efficiency_first: Focus on maximizing outfit stat efficiency"""
        def sort_key(item):
            room_key, need_data = item
            room_type = need_data['room_type']
            priority = get_room_priority(room_type)
            stat_needed = need_data['stat']
        
            # Calculate potential efficiency for this room
            available_relevant_outfits = [
                oid for oid in outfit_inventory
                if oid in outfit_mods and 
                get_outfit_bonus_for_stat(oid, stat_needed) > 0 and 
                outfit_available(oid)
            ]
        
            if available_relevant_outfits:
                # Average efficiency of available outfits for this stat
                avg_efficiency = sum(get_outfit_efficiency(oid, stat_needed) 
                                   for oid in available_relevant_outfits) / len(available_relevant_outfits)
            else:
                avg_efficiency = 0
        
            # Primary: room priority, Secondary: outfit efficiency potential
            return (priority, -avg_efficiency)
    
        return sorted(room_needs.items(), key=sort_key)

    def select_best_outfit_for_strategy(available_outfits, stat_needed, strategy):
        """Select the best outfit based on the current strategy"""
        if not available_outfits:
            return None
    
        if strategy == 'deficit_first':
            # Maximize stat bonus (raw power)
            return max(available_outfits, 
                      key=lambda oid: get_outfit_bonus_for_stat(oid, stat_needed))
    
        elif strategy == 'big_rooms_first':
            # Maximize stat bonus (same as deficit for outfit selection)
            return max(available_outfits, 
                      key=lambda oid: get_outfit_bonus_for_stat(oid, stat_needed))
    
        elif strategy == 'efficiency_first':
            # Maximize efficiency (% of total stats that match needed stat)
            return max(available_outfits, 
                      key=lambda oid: (get_outfit_efficiency(oid, stat_needed), 
                                      get_outfit_bonus_for_stat(oid, stat_needed)))
    
        elif strategy == 'hybrid':
            # Balance between efficiency and raw power
            def hybrid_score(oid):
                efficiency = get_outfit_efficiency(oid, stat_needed)
                bonus = get_outfit_bonus_for_stat(oid, stat_needed)
                normalized_bonus = bonus / 7  # Max outfit bonus is typically ~7
                return (efficiency * 0.5) + (normalized_bonus * 0.5)
        
            return max(available_outfits, key=hybrid_score)
    
        else:
            # Default to deficit_first
            return max(available_outfits, 
                      key=lambda oid: get_outfit_bonus_for_stat(oid, stat_needed))



    # ============================================================================
    # APPLY SELECTED STRATEGY
    # ============================================================================

    """ 
    FILTER OUT REDUNDANT ASSIGNMENTS - Some existing outfits may still be valid and efficient in new placement, so we keep them. 
    This step just removes any that are now redundant (dweller already has the same outfit in the database) to free them up for reassignment if needed. 
    """
    print("\n" + "-"*60)
    print("FILTERING REDUNDANT OUTFIT ASSIGNMENTS")
    print("-"*60)

    redundant_assignments = []
    for dweller_id, outfit_id in list(outfit_assignments.items()):
        # Check if this dweller already has this outfit in the database
        if dweller_id in existing_outfit_assignments and existing_outfit_assignments[dweller_id] == outfit_id:
            redundant_assignments.append((dweller_id, outfit_id))
            
    if redundant_assignments:
        print(f"Found {len(redundant_assignments)} redundant assignments (dweller already wearing outfit):")
        for dweller_id, outfit_id in redundant_assignments:
            outfit_name = outfit_mods.get(outfit_id, {}).get('name', outfit_id)
            print(f"  - Dweller {dweller_id} already has {outfit_name} - skipping")
            del outfit_assignments[dweller_id]
    else:
        print("No redundant assignments found")


    # Sort rooms based on strategy
    if outfit_strategy == 'deficit_first':
        sorted_rooms = sort_rooms_deficit_first(room_needs)
        print("\n📊 Strategy: DEFICIT FIRST - Prioritizing rooms needing most help")
    elif outfit_strategy == 'big_rooms_first':
        sorted_rooms = sort_rooms_big_rooms_first(room_needs)
        print("\n🏢 Strategy: BIG ROOMS FIRST - Prioritizing high-level/merged rooms")
    elif outfit_strategy == 'hybrid':
        sorted_rooms = sort_rooms_hybrid(room_needs)
        print("\n⚖️  Strategy: HYBRID - Balancing deficit and room size")
    elif outfit_strategy == 'efficiency_first':
        sorted_rooms = sort_rooms_efficiency_first(room_needs)
        print("\n⚡ Strategy: EFFICIENCY FIRST - Maximizing outfit stat efficiency")
    else:
        sorted_rooms = sort_rooms_deficit_first(room_needs)
        print(f"\n⚠️  Unknown strategy '{outfit_strategy}', defaulting to DEFICIT FIRST")

    # MAIN OUTFIT ASSIGNMENT LOOP
    print("\n" + "-"*60)
    print("OUTFIT ASSIGNMENT - STRATEGY-BASED OPTIMIZATION")
    print("-"*60)

    assignments_made = 0

    for room_key, need_data in sorted_rooms:
        if not any_outfit_left():
            print("\n⚠️  No more outfits available")
            break
    
        stat_needed = need_data['stat']
        deficit = need_data['deficit']
        dwellers = need_data['dwellers']
        room_type = need_data['room_type']
        priority = get_room_priority(room_type)
        value_score = get_room_value_score(room_key)

        # Get unequipped dwellers in this room
        unequipped_dwellers = [d for d in dwellers if d not in outfit_assignments]
    
        if not unequipped_dwellers:
            continue

        # Get available outfits for this stat
        relevant_outfits = [
            oid for oid in outfit_inventory
            if oid in outfit_mods and 
            get_outfit_bonus_for_stat(oid, stat_needed) > 0 and 
            outfit_available(oid)
        ]

        if not relevant_outfits:
            continue

        print(f"\n{room_key} (Priority {priority}, Value {value_score}, Deficit: {round(deficit, 1)} {stat_needed})")
    
        # Sort dwellers (lowest stat first = most benefit from outfit)
        unequipped_dwellers.sort(
            key=lambda d: dweller_stats_with_outfits.get(d, {}).get(stat_needed, 0)
        )

        # Assign outfits to dwellers in this room
        for dweller_id in unequipped_dwellers:
            if not relevant_outfits:
                break

            # Filter outfits by gender compatibility for this specific dweller
            dweller_sex = get_dweller_gender(dweller_id)
            gender_compatible_outfits = [
                oid for oid in relevant_outfits
                if outfit_manager.is_outfit_compatible(dweller_sex, oid)
            ]

            if not gender_compatible_outfits:
                print(f"  ⚠️  No gender-compatible outfits available for Dweller {dweller_id} ({dweller_sex or 'unknown sex'})")
                continue

            # Select best outfit based on strategy
            outfit_id = select_best_outfit_for_strategy(
                gender_compatible_outfits,
                stat_needed,
                outfit_strategy
            )
        
            if outfit_id is None:
                break

            # Remove from available pool
            relevant_outfits.remove(outfit_id)
            outfit_used[outfit_id] += 1
            outfit_assignments[dweller_id] = outfit_id
            outfit = outfit_mods[outfit_id]

            # Apply outfit bonuses
            dweller_stats_with_outfits[dweller_id]['Strength'] += outfit['s']
            dweller_stats_with_outfits[dweller_id]['Perception'] += outfit['p']
            dweller_stats_with_outfits[dweller_id]['Agility'] += outfit['a']
            dweller_stats_with_outfits[dweller_id]['Intelligence'] += outfit['i']
            dweller_stats_with_outfits[dweller_id]['Endurance'] += outfit['e']
            dweller_stats_with_outfits[dweller_id]['Charisma'] += outfit['c']
            dweller_stats_with_outfits[dweller_id]['Luck'] += outfit['l']

            bonus = get_outfit_bonus_for_stat(outfit_id, stat_needed)
            efficiency = round(get_outfit_efficiency(outfit_id, stat_needed) * 100, 1)
            total_bonus = get_outfit_total_bonus(outfit_id)
        
            print(f"  ✓ Assigned {outfit['name']} to Dweller {dweller_id}")
            print(f"    +{bonus} {stat_needed} ({efficiency}% efficient, +{total_bonus} total stats)")
        
            assignments_made += 1
            deficit -= bonus

            # Strategy-specific stopping conditions
            if outfit_strategy == 'deficit_first' and deficit <= 0:
                print(f"  ✓ Room deficit eliminated!")
                break
            elif outfit_strategy == 'efficiency_first' and efficiency < 60:
                print(f"  ⚠️  Efficiency threshold reached, moving to next room")
                break

    print(f"\n{'='*60}")
    print(f"OUTFIT ASSIGNMENT COMPLETE - {assignments_made} new assignments")
    print(f"{'='*60}")

    # Recalculate with outfits
    mean_finder_with_outfits = recalc_mean_finder(dweller_stats_with_outfits, sortedL, happiness_decimal)

    print("\n" + "="*60)
    print("PRODUCTION TIMES WITH OUTFITS")
    print("="*60)

    for room_key, t in mean_finder_with_outfits.items():
        if room_key[0] in TRAINING_ROOMS:
            continue
        old_time = after_balancing_times.get(room_key, 0)
        improvement = old_time - t
        improvement_pct = ((old_time - t) / old_time * 100) if old_time > 0 else 0
        print(f"{room_key} -> {t:.1f}s (was {old_time:.1f}s, {improvement_pct:+.1f}%)")

    geo_mean_new, wap_mean_new, caf_mean_new, med_mean_new, nuka_mean_new = group_means(mean_finder_with_outfits)

    print(f"\n{'='*60}")
    print("AVERAGE TIMES COMPARISON")
    print(f"{'='*60}")

    if geo_mean is not None and geo_mean_new is not None:
        improvement_pct = ((geo_mean - geo_mean_new) / geo_mean * 100)
        print(f"Power:  {round(geo_mean, 1)}s -> {round(geo_mean_new, 1)}s (Δ {round(geo_mean - geo_mean_new, 1)}s, {improvement_pct:+.1f}%)")
    if wap_mean is not None and wap_mean_new is not None:
        improvement_pct = ((wap_mean - wap_mean_new) / wap_mean * 100)
        print(f"Water:  {round(wap_mean, 1)}s -> {round(wap_mean_new, 1)}s (Δ {round(wap_mean - wap_mean_new, 1)}s, {improvement_pct:+.1f}%)")
    if caf_mean is not None and caf_mean_new is not None:
        improvement_pct = ((caf_mean - caf_mean_new) / caf_mean * 100)
        print(f"Food:   {round(caf_mean, 1)}s -> {round(caf_mean_new, 1)}s (Δ {round(caf_mean - caf_mean_new, 1)}s, {improvement_pct:+.1f}%)")
    if med_mean is not None and med_mean_new is not None:
        improvement_pct = ((med_mean - med_mean_new) / med_mean * 100)
        print(f"Medbay: {round(med_mean, 1)}s -> {round(med_mean_new, 1)}s (Δ {round(med_mean - med_mean_new, 1)}s, {improvement_pct:+.1f}%)")
    if nuka_mean is not None and nuka_mean_new is not None:
        improvement_pct = ((nuka_mean - nuka_mean_new) / nuka_mean * 100)
        print(f"NukaCola: {round(nuka_mean, 1)}s -> {round(nuka_mean_new, 1)}s (Δ {round(nuka_mean - nuka_mean_new, 1)}s, {improvement_pct:+.1f}%)")

    # Outfit assignment summary
    print(f"\n{'='*60}")
    print("OUTFIT ASSIGNMENT SUMMARY")
    print(f"{'='*60}")

    new_assignments = {k: v for k, v in outfit_assignments.items() if k not in existing_outfit_assignments}
    kept_existing = {k: v for k, v in outfit_assignments.items() if k in existing_outfit_assignments}

    print(f"Strategy Used: {outfit_strategy}")
    print(f"Total outfits assigned: {len(outfit_assignments)}")
    print(f"  - Pre-existing (kept): {len(kept_existing)}")
    print(f"  - Newly assigned: {len(new_assignments)}")
    print(f"  - Relocated: {len(outfits_to_relocate)}")

    remaining = sum(outfit_inventory[oid] - outfit_used.get(oid, 0) for oid in outfit_inventory)
    print(f"Remaining unassigned outfits: {remaining}")

    # Strategy-specific metrics
    if outfit_strategy == 'efficiency_first':
        total_efficiency = 0
        count = 0
        for dweller_id, outfit_id in new_assignments.items():
            dweller_room = None
            for room_key, dwellers in sortedL.items():
                if dweller_id in dwellers:
                    dweller_room = room_key
                    break
            if dweller_room:
                _, stat, _ = parse_room(dweller_room)
                eff = get_outfit_efficiency(outfit_id, stat)
                total_efficiency += eff
                count += 1
    
        if count > 0:
            avg_efficiency = (total_efficiency / count) * 100
            print(f"Average outfit efficiency: {avg_efficiency:.1f}%")

    # Plotting
    exclude = {"Gym", "Armory", "Dojo", "Classroom"}
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
        'balancing_config': {
            'balance_threshold': balancing_config.balance_threshold,
            'max_passes': balancing_config.max_passes,
            'cross_stat_balancing': balancing_config.enable_cross_stat_balancing,
            'priorities': balancing_config.room_priorities
        },
        'swap_history': swap_logger.swap_history,
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

            dweller_all_stats = working_stats.get(dweller_id, {})
            
            dweller_entry = {
                'id': dweller_id,
                'name': full_name if full_name else f"Dweller {dweller_id}",
                'assigned_room': assigned_room_info,
                'previous_room': previous_room_info,
                'primary_stat': stat,
                'all_stats': dweller_all_stats,
                'dweller_moved': moved_room_info
            }

         
            if dweller_id in outfit_assignments:
                outfit_id = outfit_assignments[dweller_id]
                outfit = outfit_mods[outfit_id]
                
                previous_owner_info = None
                if outfit_id in outfit_previous_owners_list:

                    previous_owners = outfit_previous_owners_list[outfit_id]
                    
                    # Find if any previous owner is different from current dweller and hasn't been reassigned
                    for prev_owner_id in previous_owners:

                        if prev_owner_id == dweller_id:
                            continue
                        
                        # Check if this previous owner no longer has this outfit
                        current_outfit_for_prev_owner = outfit_assignments.get(prev_owner_id)
                        if current_outfit_for_prev_owner != outfit_id:
                            # This previous owner lost their outfit - record them
                            prev_owner_dweller = next(
                                (d for d in dwellers_list if str(d.get('serializeId')) == prev_owner_id),
                                None
                            )
                            if prev_owner_dweller:
                                prev_name = f"{prev_owner_dweller.get('name', '')} {prev_owner_dweller.get('lastName', '')}".strip()
                                previous_owner_info = {
                                    'dweller_id': prev_owner_id,
                                    'dweller_name': prev_name if prev_name else f"Dweller {prev_owner_id}"
                                }
                                # Remove this owner from the list so they're not assigned twice
                                outfit_previous_owners_list[outfit_id].remove(prev_owner_id)
                                break
                
                dweller_entry['outfit'] = {
                    'outfit_id': outfit_id,
                    'outfit_name': outfit.get('name', 'Unknown'),
                    'strength_bonus': outfit.get('s', 0),
                    'perception_bonus': outfit.get('p', 0),
                    'agility_bonus': outfit.get('a', 0),
                    'intelligence_bonus': outfit.get('i', 0),
                    'endurance_bonus': outfit.get('e', 0),
                    'charisma_bonus': outfit.get('c', 0),
                    'luck_bonus': outfit.get('l', 0),
                    'previous_owner': previous_owner_info
                }

            optimization_results['dweller_assignments'].append(dweller_entry)

    for room_key, dwellers_in_room in sortedL.items():
        room_id = f"{room_key[0]}_{room_key[1]}_{room_key[2]}_{room_key[3]}"
        dweller_list = []
        for dweller_id in dwellers_in_room:
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
        'food_avg': round(caf_mean_new, 2) if caf_mean_new else None,
        'medbay_avg': round(med_mean_new, 2) if med_mean_new else None,
        'nukacola_avg': round(nuka_mean_new, 2) if nuka_mean_new else None
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
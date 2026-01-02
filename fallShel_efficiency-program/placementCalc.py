from ast import Pass
import os
import json
from queue import Empty
import sqlite3
from PIL import Image
import numpy


conn = sqlite3.connect("vault.db")
cursor = conn.cursor()


downloads_folder = os.path.expanduser(r"~\Downloads")
file_path = os.path.join(downloads_folder, "Vault2.json") 

# Open and read the JSON file
with open(file_path, "r", encoding="utf-8") as file:
    data = json.load(file)


vault_file = "vault_map.txt"
dwellers_list = data["dwellers"]["dwellers"]

geothermal = []
waterPlant = []
cafeteria = []
gym = []
armory = []
dojo = []
allStats = []
bestGeo = []
bestCaf = []
bestWaP = []
secbestGeo = []
secbestCaf = []
secbestWaP = []
worstGeo = []
worstCaf = []
worstWaP = []
sortedL = {}
Stats = {}

# initialize dweller_stats
dweller_stats = {}

try:
    with open(vault_file, "r", encoding="utf-8") as file:
        for line in file:
            rooms = line.strip().split(" | ")

            for room in rooms:
                if room == "Empty":
                    continue

                # Determine merge size
                if "MergeLevel: 3" in room:
                    size_val = 9
                elif "MergeLevel: 2" in room:
                    size_val = 6
                else:
                    size_val = 3

                # Determine level
                if "level= 3" in room:
                    lvl = 3
                elif "level= 2" in room:
                    lvl = 2
                else:
                    lvl = 1

                # Append one entry per group
                if "Energy2" in room:
                    geothermal.append(f"En2-lvl{lvl}-size{size_val}-1")
                elif "Hydroponic" in room:
                    cafeteria.append(f"Hyd-lvl{lvl}-size{size_val}-1")
                elif "Water2" in room:
                    waterPlant.append(f"Wt2-lvl{lvl}-size{size_val}-1")
                elif "Geothermal" in room:
                    geothermal.append(f"Goe-lvl{lvl}-size{size_val}-1")
                elif "WaterPlant" in room:
                    waterPlant.append(f"WP-lvl{lvl}-size{size_val}-1")
                elif "Cafeteria" in room:
                    cafeteria.append(f"Caf-lvl{lvl}-size{size_val}-1")
                elif "Gym" in room:
                    gym.append(f"Arm-lvl{lvl}-size{size_val}-1")
                elif "Armory" in room:
                    armory.append(f"Gym-lvl{lvl}-size{size_val}-1")
                elif "Dojo" in room:
                    dojo.append(f"Dojo-lvl{lvl}-size{size_val}-1")
except FileNotFoundError:
    print(f"{vault_file} not found.")
except Exception as e:
    print(f"An error occurred: {e}")

RoomLists = [geothermal, waterPlant, cafeteria]
TrainingRoomList = [gym, armory, dojo]

for lst in RoomLists:
    i = 0 
    while i < len(lst):
        val = lst[i]
        if "size9" in val:
            del lst[i+1 : i+1+8]
            i += 1
        elif "size6" in val:
            del lst[i+1 : i+1+5]
            i += 1
        elif "size3" in val:
            del lst[i+1 : i+1+2]
            i += 1
        else:
            i += 1

    count = 2
    for x in range(len(lst)):
        for j in range(x + 1, len(lst)):
            if lst[x] == lst[j]:
                parts = lst[x].rsplit("-",1)
                lst[x] = parts[0] + "-" +str(count)
                count += 1

# sort level        
for sortlst in RoomLists:
    for i in range(len(sortlst) - 1):
        for j in range(len(sortlst) - i - 1):

            left_val = int(sortlst[j][-1:])
            right_val = int(sortlst[j+1][-1:])

            if left_val < right_val:
                sortlst[j], sortlst[j+1] = sortlst[j+1], sortlst[j]

numDwellers = 0
total_happiness = 0

for d in dwellers_list:
    serialize_id = d.get("serializeId")
    happiness = d.get("happiness", {}).get("happinessValue", 0)
    stats = ('Strength', 'Perception', 'Agility')
    numDwellers += 1
    total_happiness += happiness

    cursor.execute(
        "SELECT dweller_id, StatName, Value, Mod FROM Stats WHERE StatName IN (?, ?, ?) AND dweller_id = ?",
        (stats[0], stats[1], stats[2], serialize_id)
    )
    allStats = cursor.fetchall()
    Stats[serialize_id] = allStats

    stat_map = {}
    for _dwid, statname, value, mode in allStats:
        stat_map[statname] = value + mode
    dweller_stats[str(serialize_id)] = stat_map

    dwellerbeststats = {}
    dwellersecbeststats = {}
    dwellerworststats = {}

    highest = -1
    second_highest = -1
    lowest = float("inf")

    best_stat = None
    second_stat = None
    worst_stat = None

    for dwellerid, statname, value, mode in allStats:
        if dwellerid == serialize_id:
            total = value + mode

            # best
            if total > highest:
                second_highest = highest
                second_stat = best_stat

                highest = total
                best_stat = statname

            # second best
            elif total > second_highest:
                second_highest = total
                second_stat = statname

            # worst
            if total < lowest:
                lowest = total
                worst_stat = statname

    if best_stat == "Strength":
        bestGeo.append(f"{dwellerid} - {highest} ")
    elif best_stat == "Perception":
        bestWaP.append(f"{dwellerid} - {highest} ")
    elif best_stat == "Agility":
        bestCaf.append(f"{dwellerid} - {highest} ")

    if second_stat == "Strength":
        secbestGeo.append(f"{dwellerid} - {second_highest} ")
    elif second_stat == "Perception":
        secbestWaP.append(f"{dwellerid} - {second_highest} ")
    elif second_stat == "Agility":
        secbestCaf.append(f"{dwellerid} - {second_highest} ")

    if worst_stat == "Strength":
        worstGeo.append(f"{dwellerid} - {lowest} ")
    elif worst_stat == "Perception":
        worstWaP.append(f"{dwellerid} - {lowest} ")
    elif worst_stat == "Agility":
        worstCaf.append(f"{dwellerid} - {lowest} ")

    dwellerbeststats[dwellerid] = f"{highest} - {best_stat}"
    dwellersecbeststats[dwellerid] = f"{second_highest} - {second_stat}"
    dwellerworststats[dwellerid] = f"{lowest} - {worst_stat}"

    print(dwellerbeststats)
    print(dwellersecbeststats)
    print(dwellerworststats)

vault_happiness = round(total_happiness / numDwellers) if numDwellers > 0 else 0
print(f"\nVault Average Happiness: {vault_happiness}%\n")

bestList = [bestGeo, bestWaP, bestCaf, secbestCaf, secbestWaP, secbestGeo, worstCaf, worstGeo, worstWaP]

for sortlst in bestList:
    for i in range(len(sortlst) - 1):
        for j in range(len(sortlst) - i - 1):

            left_val = int(sortlst[j].split(" - ")[1])
            right_val = int(sortlst[j+1].split(" - ")[1])

            if left_val < right_val:
                sortlst[j], sortlst[j+1] = sortlst[j+1], sortlst[j]
conn.close()

def get_unassignedID(geolist, caflist, Waplist):
    combined = []
    combined.append(geolist)
    combined.append(caflist)
    combined.append(Waplist)
    unassignedID_list= [item for sublist in combined for item in sublist]
    return unassignedID_list 

def get_unassigned_stat(stats, list):
    ids = set(s.strip() for s in list)
    stats[:] = [s for s in stats if s.split(" - ")[0].strip() in  ids]

def extract_ids(data):
    return [x.split(" - ")[0].strip() for x in data]

def assign_rooms(rooms, dwellers):
    for room in rooms:
        room_parts = room.split("-")
        size = room_parts[2]

        size_map = {
            "size9": 6,
            "size6": 4,
            "size3": 2
        }

        LIMIT = size_map.get(size, 0)
        key = tuple(room_parts)
        current = len(sortedL.get(key, []))
        take = LIMIT - current

        if take > 0:
            assigned = dwellers[:take]
            del dwellers[:take]
            sortedL.setdefault(key, []).extend(assigned)

# assigning values
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

# Round 2
secRdwellers = get_unassignedID(sec_geo_dwellers, sec_caf_dwellers, sec_wap_dwellers)
get_unassigned_stat(secbestGeo, secRdwellers)
get_unassigned_stat(secbestCaf, secRdwellers)
get_unassigned_stat(secbestWaP, secRdwellers)
assign_rooms(geothermal, sec_geo_dwellers)
assign_rooms(waterPlant, sec_wap_dwellers) 
assign_rooms(cafeteria, sec_caf_dwellers)

# Round 3
thiRdwellers= get_unassignedID(thi_geo_dwellers, thi_caf_dwellers, thi_wap_dwellers)
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


# TRAINING SECTION  

# rebuild stat lists ONLY from leftover dwellers
get_unassigned_stat(worstGeo, leftOver)
get_unassigned_stat(worstCaf, leftOver)
get_unassigned_stat(worstWaP, leftOver)

# sort weakest first (low stat to high stat)
for sortlst in (worstGeo, worstCaf, worstWaP):
    sortlst.sort(key=lambda x: int(x.split(" - ")[1]))

train_geo = extract_ids(worstGeo)
train_caf = extract_ids(worstCaf)
train_wap = extract_ids(worstWaP)

assign_rooms(gym, train_geo)       
assign_rooms(dojo, train_caf)      
assign_rooms(armory, train_wap)   


# Round 2
get_unassigned_stat(secbestGeo, leftOver)
get_unassigned_stat(secbestCaf, leftOver)
get_unassigned_stat(secbestWaP, leftOver)

for sortlst in (secbestGeo, secbestCaf, secbestWaP):
    sortlst.sort(key=lambda x: int(x.split(" - ")[1]))

train_geo_2 = extract_ids(secbestGeo)
train_caf_2 = extract_ids(secbestCaf)
train_wap_2 = extract_ids(secbestWaP)

assign_rooms(gym, train_geo_2)
assign_rooms(dojo, train_caf_2)
assign_rooms(armory, train_wap_2)


# Round 3
get_unassigned_stat(bestGeo, leftOver)
get_unassigned_stat(bestCaf, leftOver)
get_unassigned_stat(bestWaP, leftOver)

for sortlst in (bestGeo, bestCaf, bestWaP):
    sortlst.sort(key=lambda x: int(x.split(" - ")[1]))

train_geo_3 = extract_ids(bestGeo)
train_caf_3 = extract_ids(bestCaf)
train_wap_3 = extract_ids(bestWaP)

assign_rooms(gym, train_geo_3)
assign_rooms(dojo, train_caf_3)
assign_rooms(armory, train_wap_3)

    
print("\nTraining Rooms:")
for room, dwellers in sortedL.items():
    if room[0] in ("Gym", "Arm", "Dojo"):
        print(f"Room: {room} -> Dwellers: {', '.join(dwellers)}")
print("")

allDwellerIDs = {str(d["serializeId"]) for d in dwellers_list}

assigned = set()
for dwellers in sortedL.values():
    assigned.update(dwellers)

finalRemaining = list(allDwellerIDs - assigned)

print("\nFinal Unassigned Dwellers:")
print(", ".join(finalRemaining))


# Plot Section

from matplotlib import pyplot as plt
from collections import defaultdict

rooms_by_type = defaultdict(list)

ROOM_CODE_MAP = {
    "Goe": ("Power", "Strength"),
    "En2": ("Power", "Strength"),
    "WP":  ("Water", "Perception"),
    "Wt2": ("Water", "Perception"),
    "Caf": ("Food", "Agility"),
    "Hyd": ("Food", "Agility"),
}

BASE_POOL = {
    "Power": 1320,
    "Food": 960,
    "Water": 960
}

SIZE_MULTIPLIER = {
    "size3": 1,
    "size6": 2,
    "size9": 3
}

ROOM_CAPACITY = {
    "size3": 2,
    "size6": 4,
    "size9": 6
}

def room_capacity(room):
    return ROOM_CAPACITY[room[2]]


def parse_room(room_key):
    # room_key is tuple: ('Goe','lvl3','size6','1')
    code = room_key[0]
    size = room_key[2]

    room_type, stat = ROOM_CODE_MAP.get(code, (None, None))
    return room_type, stat, size

def get_room_production_time(room_key, dwellers, dweller_stats, happiness=1.0):
    room_type, stat, size = parse_room(room_key)
    if room_type is None:
        return None

    pool = BASE_POOL[room_type] * SIZE_MULTIPLIER[size]

    total_stat = sum(dweller_stats[d][stat] for d in dwellers)
    if total_stat == 0:
        return None

    return round(pool / (total_stat * happiness), 1)

mean_finder = {}

print("\nTIME")
for room_key, dwellers in sortedL.items():
    time_sec = get_room_production_time(
        room_key,
        dwellers,
        dweller_stats,
        happiness=vault_happiness/100
    )

    if time_sec:
        print(f"{room_key} -> {time_sec} seconds")
        mean_finder[room_key] = time_sec

# initialize accumulators before the loop
geo_sum_of_time = 0.0
geo_total = 0
wap_sum_of_time = 0.0
wap_total = 0
caf_sum_of_time = 0.0
caf_total = 0

# iterate items() to get (room_key, time) pairs
for room, time in mean_finder.items():
    roomtype = room[0]

    if roomtype in ("Goe", "En2"):
        geo_sum_of_time += time
        geo_total += 1

    elif roomtype in ("WP", "Wt2"):
        wap_sum_of_time += time
        wap_total += 1

    elif roomtype in ("Caf", "Hyd"):
        caf_sum_of_time += time
        caf_total += 1

# compute means after counts are complete and guard against zero
geo_mean = (geo_sum_of_time / geo_total) if geo_total > 0 else None
wap_mean = (wap_sum_of_time / wap_total) if wap_total > 0 else None
caf_mean = (caf_sum_of_time / caf_total) if caf_total > 0 else None

print("\nAVERAGE TIME")
if geo_total > 0:
    print(f"Geothermal Average Time: {round(geo_mean,1)} seconds")

if wap_total > 0:
    print(f"Water Plant Average Time: {round(wap_mean,1)} seconds")

if caf_total > 0:
    print(f"Cafeteria Average Time: {round(caf_mean,1)} seconds")

upper_mean = []
lower_mean = []

for room, time in mean_finder.items():
    roomtype = room[0]

    if roomtype in ("Goe", "En2"):
        if time > geo_mean:
            upper_mean.append(f"{room} -> {time}")
        else:
            lower_mean.append(f"{room} -> {time}")

    elif roomtype in ("WP", "Wt2"):
        if time > wap_mean:
            upper_mean.append(f"{room} -> {time}")
        else:
            lower_mean.append(f"{room} -> {time}")

    elif roomtype in ("Caf", "Hyd"):
        if time > caf_mean:
            upper_mean.append(f"{room} -> {time}")
        else:
            lower_mean.append(f"{room} -> {time}")

print("\nRooms Above Average Time:")
for entry in upper_mean:
    print(f"{entry} seconds")

print("\nRooms Below Average Time:")
for entry in lower_mean:
    print(f"{entry} seconds")

# Before balancing times
before_times = {room: get_room_production_time(room, dwellers, dweller_stats, happiness=vault_happiness/100)
                for room, dwellers in sortedL.items()}

BALANCE_THRESHOLD = 5.0  

print("\nSTAT ADJUSTMENT SUGGESTIONS")

for room_key, time in mean_finder.items():
    room_type, stat, size = parse_room(room_key)

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
    current_total = sum(dweller_stats[d][stat] for d in dwellers)

    ideal_total = pool / (target * (vault_happiness / 100))
    diff = round(ideal_total - current_total, 1)

    if abs(diff) < 0.5:
        status = "Balanced"
    elif diff > 0:
        status = f"Needs +{diff} {stat}"
    else:
        status = f"Remove {abs(diff)} {stat}"

    print(f"{room_key} | Time: {time}s | {status}")


def get_total_stat(room_key):
    room_type, stat, _ = parse_room(room_key)
    return sum(dweller_stats[d][stat] for d in sortedL[room_key])

def best_dweller(room_key):
    room_type, stat, _ = parse_room(room_key)
    return max(sortedL[room_key], key=lambda d: dweller_stats[d][stat])

def worst_dweller(room_key):
    room_type, stat, _ = parse_room(room_key)
    return min(sortedL[room_key], key=lambda d: dweller_stats[d][stat])


print("\nAUTO BALANCING ROOMS")

ROOM_GROUPS = {
    "Power": ("Goe", "En2"),
    "Water": ("WP", "Wt2"),
    "Food": ("Caf", "Hyd")
}  

TRAINING_ROOMS = {"Arm", "Dojo", "Gym"}

def has_space(room_key):
    _, _, size = parse_room(room_key)
    return len(sortedL[room_key]) < ROOM_CAPACITY[size]

def recalc_times():
    mean_finder.clear()
    for room_key, dwellers in sortedL.items():
        t = get_room_production_time(
            room_key,
            dwellers,
            dweller_stats,
            happiness=vault_happiness / 100
        )
        if t:
            mean_finder[room_key] = t

def is_balanced():
    for room_key, time in mean_finder.items():
        room_type, _, _ = parse_room(room_key)

        if room_type == "Power" and abs(time - geo_mean) > BALANCE_THRESHOLD:
            return False
        if room_type == "Water" and abs(time - wap_mean) > BALANCE_THRESHOLD:
            return False
        if room_type == "Food" and abs(time - caf_mean) > BALANCE_THRESHOLD:
            return False

    return True

# More is not always better 
MAX_PASSES = 12 
pass_num = 1

# corrected balancing loop
while pass_num <= MAX_PASSES:
    recalc_times()  # refresh mean_finder

    # recompute group means
    geo_times = [t for r,t in mean_finder.items() if r[0] in ("Goe","En2")]
    wap_times = [t for r,t in mean_finder.items() if r[0] in ("WP","Wt2")]
    caf_times = [t for r,t in mean_finder.items() if r[0] in ("Caf","Hyd")]

    geo_mean = (sum(geo_times)/len(geo_times)) if geo_times else None
    wap_mean = (sum(wap_times)/len(wap_times)) if wap_times else None
    caf_mean = (sum(caf_times)/len(caf_times)) if caf_times else None

    # Sadly, we will never see this message
    if is_balanced():
        print(f"\nBalanced after {pass_num} passes")
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

        # check after weakest/strongest are defined
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

    pass_num += 1

    # Build `after_times` for all rooms so keys match `before_times` even if
    # `get_room_production_time` returns None for training rooms. This prevents
    # KeyError when comparing before/after dictionaries.
    after_times = {
        room: get_room_production_time(room, dwellers, dweller_stats, happiness=vault_happiness/100)
        for room, dwellers in sortedL.items()
    }


print("")
for room, dwellers in sortedL.items():
    print(f"Room: {room} -> Dwellers: {', '.join(dwellers)}")
print("")

print("\n NEW TIME")
for room_key, dwellers in sortedL.items():
    time_sec = get_room_production_time(
        room_key,
        dwellers,
        dweller_stats,
        happiness=vault_happiness/100
    )

    if time_sec:
        print(f"{room_key} -> {time_sec} seconds")
        mean_finder[room_key] = time_sec
       
print("\nNEW AVERAGE TIME")
if geo_total > 0:
    print(f"Geothermal Average Time: {round(geo_mean,1)} seconds")

if wap_total > 0:
    print(f"Water Plant Average Time: {round(wap_mean,1)} seconds")

if caf_total > 0:
    print(f"Cafeteria Average Time: {round(caf_mean,1)} seconds")


rooms = list(before_times.keys())

# Ensure `after_times` exists (balancing loop may not run) and align keys
try:
    after_times
except NameError:
    after_times = {room: None for room in sortedL}

# Convert None -> NaN so matplotlib can handle missing values
before = [numpy.nan if before_times.get(r) is None else before_times[r] for r in rooms]
after = [numpy.nan if after_times.get(r) is None else after_times[r] for r in rooms]

# Use numpy arrays for numeric operations
before_arr = numpy.array(before, dtype=float)
after_arr = numpy.array(after, dtype=float)

x = range(len(rooms))  

plt.figure(figsize=(12,6))
plt.bar(x, before_arr, width=0.4, label='Before Balancing', align='edge')
plt.bar(x, after_arr, width=-0.4, label='After Balancing', align='edge')

plt.xticks(x, [f"{r[0]}-{r[1]}-{r[3]}" for r in rooms], rotation=45)  # show room type and level
plt.ylabel("Production Time (s)")
plt.title("Room Production Times Before and After Balancing")
plt.legend()
plt.tight_layout()
plt.show()
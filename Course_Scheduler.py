# Course Scheduler for Fall 2025 with Enhanced Logic and Diagnostics
import pandas as pd
import numpy as np
from collections import defaultdict
from openpyxl import load_workbook

# === Load Groupwise Course Info ===
groupwise_df = pd.read_excel("groupwise_course_tags_fall2025.xlsx")
groupwise_df = groupwise_df.dropna(subset=["Course", "Track", "Semester"])

# Normalize text
groupwise_df["Course"] = groupwise_df["Course"].str.strip()
groupwise_df["Track"] = groupwise_df["Track"].str.strip()
groupwise_df["Semester"] = groupwise_df["Semester"].str.strip()
groupwise_df["Group"] = groupwise_df["Track"] + "_" + groupwise_df["Semester"]

# === Define Rooms ===
room_df = pd.DataFrame({
    "Room": [
        "Amphitheater", "101", "102", "151", "152", "153", "154", "155", "10", "12"
    ],
    "Capacity": [201, 95, 49, 90, 48, 48, 16, 16, 18, 15]
})

# === Define Time Slots ===
time_slots = [
    "Mon_AM", "Mon_PM", "Tue_AM", "Tue_PM", "Wed_AM", "Wed_PM", "Thu_AM", "Fri_AM", "Fri_PM"
]

# === Derive Course Demand and Type ===
course_info = groupwise_df.groupby("Course").agg(
    MandatoryGroups=("GroupTag", lambda x: sum(x == "mandatory")),
    TotalGroups=("Group", "nunique"),
    Type=("Type", "first")
).reset_index()

# Sort by priority (mandatory groups first)
course_info = course_info.sort_values(by=["MandatoryGroups", "TotalGroups"], ascending=False)

# === Load Student Estimates from 2024 and Merge ===
student_counts_2024 = pd.read_csv("number-of-students-fall-2024-extracted.csv")
student_counts_2024.columns = ["Course", "EstimatedStudents"]

# Merge with current course_info
course_info = course_info.merge(student_counts_2024, on="Course", how="left")
course_info["EstimatedStudents"] = course_info["EstimatedStudents"].fillna(0).astype(int)

 
# Sort by: EstimatedStudents first, then MandatoryGroups, then TotalGroups
course_info = course_info.sort_values(by=["EstimatedStudents", "MandatoryGroups", "TotalGroups"], ascending=[False, False, False])

def is_conflicting(existing_half, new_half):
    return (
        existing_half == new_half
        or "Long" in (existing_half, new_half)
    )

# === Assignment Structures ===
assignments = []
room_occupancy = {
    slot: {"H1": set(), "H2": set()} for slot in time_slots
}
group_occupancy = defaultdict(set)
day_load = defaultdict(int)
half_load = {slot: {"H1": 0, "H2": 0} for slot in time_slots}
unassigned = []
diagnostics = {}
evicted_courses = []
conflict_log = defaultdict(list)  # slot → list of (course, room, half, conflicting_groups)




def assign_course(course, ctype, groups, priority=True, can_preempt=False, ignore_conflicts=False):
    est_students = course_info.loc[course_info.Course == course, 'EstimatedStudents'].values[0]
    mandatory_groups = groupwise_df[(groupwise_df["Course"] == course) & (groupwise_df["GroupTag"] == "mandatory")]["Group"].unique()
    
    #regular_groups = [g for g in groups if g not in mandatory_groups]
    # Consider all groups (including mandatory) for soft conflict detection
    conflict_groups_for_penalty = groups

    preferred_slots = sorted(time_slots, key=lambda s: day_load[s.split("_")[0]])
    conflict_trace = []
    
    alpha = 3.0  # weight for soft conflict
    beta = 1.0   # weight for imbalance
    best_choice = None
    best_penalty = float('inf')

    for slot in preferred_slots:
        for half in (["Long"] if ctype == "L" else ["H1", "H2"]):
            for _, r in room_df.sort_values(by='Capacity', ascending=False).iterrows():
                room = r.Room

                # Check if room is occupied
                occupied = (room in room_occupancy[slot]["H1"]) or (room in room_occupancy[slot]["H2"])
                if ctype != "L" and room not in room_occupancy[slot][half]:
                    occupied = False
                if occupied:
                    continue

                # Check hard conflicts for mandatory groups
                #conflicting_mandatory = [g for g in mandatory_groups if slot in group_occupancy[g]]
                #real_conflict = [g for g in conflicting_mandatory if not any(kw in g.upper() for kw in ["TU", "À", "5"])]

                conflicting_mandatory = [
                    g for g in mandatory_groups
                    if any(
                        is_conflicting(existing_half, half)
                        for (s, existing_half) in group_occupancy[g]
                        if s == slot
                    )
                ]
                real_conflict = [g for g in conflicting_mandatory if not any(kw in g.upper() for kw in ["TU", "À", "5"])]

                # Extra check: avoid conflicts between mandatory courses
                if not ignore_conflicts:
                    conflict_with_other_mandatory = False
                    for a in assignments:
                        if a["TimeSlot"] == slot and is_conflicting(a["Half"], half):
                            other_course = a["Course"]
                            other_mandatory = groupwise_df[
                                (groupwise_df["Course"] == other_course) &
                                (groupwise_df["GroupTag"] == "mandatory")
                            ]["Group"].unique()

                            shared_mandatory = set(mandatory_groups).intersection(set(other_mandatory))
                            if shared_mandatory:
                                conflict_trace.append((slot, room, half, list(shared_mandatory)))
                                conflict_with_other_mandatory = True
                                break  # no need to check further

                    if conflict_with_other_mandatory:
                        continue  # skip this slot due to hard mandatory conflict
                                
            
                if real_conflict and not ignore_conflicts:
                    conflict_trace.append((slot, room, half, real_conflict))
                    conflict_log[slot].append({
                        "Course": course,
                        "Room": room,
                        "Half": half,
                        "ConflictsWithGroups": real_conflict
                    })

                    if can_preempt:
                        for i, a in enumerate(assignments):
                            if a["TimeSlot"] == slot and a["Room"] == room and a["Half"] == half:
                                target_course = a["Course"]
                                target_mandatory = course_info.loc[course_info.Course == target_course, "MandatoryGroups"].values[0]
                                # Only evict if current course has more mandatory groups
                                if len(mandatory_groups) > target_mandatory:
                                    # Remove assignment and clear occupancy
                                    assignments.pop(i)
                                    room_occupancy[slot]["H1"].discard(room)
                                    room_occupancy[slot]["H2"].discard(room)
                                    group_tags = groupwise_df[groupwise_df["Course"] == target_course]["Group"].unique()
                                    for g in group_tags:
                                        group_occupancy[g].discard(slot)

                                    # Add for later reassignment
                                    target_type = course_info.loc[course_info.Course == target_course, "Type"].values[0]
                                    evicted_courses.append({
                                        "Course": target_course,
                                        "Type": target_type,
                                        "Groups": group_tags
                                    })

                                    print(f"🔥 Evicted {target_course} to make room for {course}")
                                    return assign_course(course, ctype, groups, priority, can_preempt=False)

                    continue  # skip this slot               
                


                # Total number of groups this course is intended for
                total_course_groups = len(groups) if len(groups) > 0 else 1  # avoid division by 0

                
                conflicting_groups = [
                    g for g in conflict_groups_for_penalty
                    if any(
                        is_conflicting(existing_half, half)
                        for (s, existing_half) in group_occupancy.get(g, set())
                        if s == slot
                    )
                ]

                conflict_score = len(conflicting_groups) / total_course_groups


                # penalty for day imbalance
                tentative_day_load = day_load.copy()
                tentative_day_load[slot.split("_")[0]] += 1
                slot_std = np.std(list(tentative_day_load.values()))

                # penalty for half-slot imbalance (only relevant for short courses)
                h_load_std = 0.0
                if ctype != "L":
                    tentative_half_load = half_load[slot].copy()
                    tentative_half_load[half] += 1
                    h_load_std = np.std(list(tentative_half_load.values()))

                # final penalty
                total_penalty = alpha * conflict_score + beta * slot_std + 0.3 * h_load_std


                if total_penalty < best_penalty:
                    best_choice = (slot, room, half, conflict_score)
                    best_penalty = total_penalty

    if best_choice:
        slot, room, half, conflict_score = best_choice
        if ctype == "L":
            room_occupancy[slot]["H1"].add(room)
            room_occupancy[slot]["H2"].add(room)
        else:
            room_occupancy[slot][half].add(room)

        for g in groups:
            # Always add the actual half
            group_occupancy[g].add((slot, half))

            # Ensure Long implies H1 and H2 occupancy (for conflict detection)
            if half == "Long":
                group_occupancy[g].add((slot, "H1"))
                group_occupancy[g].add((slot, "H2"))
            elif half in {"H1", "H2"}:
                group_occupancy[g].add((slot, "Long"))

        assignments.append({
            "Course": course,
            "TimeSlot": slot,
            "Room": room,
            "Half": half,
            "SoftConflict": conflict_score > 0
        })

        day_load[slot.split("_")[0]] += 1
        if ctype != "L":
            half_load[slot][half] += 1

        return True

    diagnostics[course] = "Blocked by mandatory group conflict in all slots:\n" + "\n".join(
        f"  {slot} @ {room} ({half}): " + ", ".join(conflict_groups)
        for slot, room, half, conflict_groups in conflict_trace
    )
    return False

# === Assign Courses ===
for _, row in course_info.iterrows():
    course = row.Course
    ctype = row.Type
    groups = groupwise_df[groupwise_df.Course == course].Group.unique()
    is_mandatory = row.MandatoryGroups > 0

    success = assign_course(course, ctype, groups, priority=True)

    if not success and not is_mandatory:
        success = assign_course(course, ctype, groups, priority=False)

    if not success and is_mandatory:
        success = assign_course(course, ctype, groups, priority=True, can_preempt=True)

    # 🆕 Force even hard conflicts if all else fails
    if not success and is_mandatory:
        success = assign_course(course, ctype, groups, priority=False, can_preempt=False, ignore_conflicts=True)
        if success:
            print(f"🚨 Forcibly assigned {course} despite hard mandatory group conflicts.")

    if not success and course not in unassigned:
        unassigned.append(course)



# === Second pass: try to reassign evicted courses ===
print("\n=== Reassignment Pass for Evicted Courses ===")
for e in evicted_courses:
    course = e["Course"]
    ctype = e["Type"]
    groups = e["Groups"]

    reassigned = (
        assign_course(course, ctype, groups, priority=True) or
        assign_course(course, ctype, groups, priority=False) or
        assign_course(course, ctype, groups, priority=True, can_preempt=True) or
        assign_course(course, ctype, groups, priority=False, ignore_conflicts=True)
    )

    if not reassigned:
        print(f"⚠️ Could not reassign evicted course: {course}")
        unassigned.append(course)


# === Second Pass: Try to Reduce Soft Conflicts ===
print("\n=== 🛠️ Soft Conflict Reassignment Pass ===")

# Store current assignments for rollback
course_to_assignment = {
    a["Course"]: a.copy() for a in assignments
    if a["SoftConflict"]
}

conflicted_courses = list(course_to_assignment.keys())
print(f"🔍 Found {len(conflicted_courses)} course(s) with soft conflicts to review.")
        
        

        
        
# Remove conflicted courses from current assignments and occupancy
for course in conflicted_courses:
    prev = course_to_assignment[course]
    slot = prev["TimeSlot"]
    room = prev["Room"]
    half = prev["Half"]
    ctype = course_info.loc[course_info.Course == course, "Type"].values[0]
    groups = groupwise_df[groupwise_df.Course == course]["Group"].unique()

    # Remove from assignments
    assignments = [a for a in assignments if a["Course"] != course]

    # Free room
    if half == "Long":
        room_occupancy[slot]["H1"].discard(room)
        room_occupancy[slot]["H2"].discard(room)
    else:
        room_occupancy[slot][half].discard(room)

    # Free groups
    for g in groups:
        group_occupancy[g].discard((slot, half))
        if half == "Long":
            group_occupancy[g].discard((slot, "H1"))
            group_occupancy[g].discard((slot, "H2"))
        elif half in {"H1", "H2"}:
            group_occupancy[g].discard((slot, "Long"))

    # Adjust load
    day_load[slot.split("_")[0]] -= 1
    if ctype != "L":
        half_load[slot][half] -= 1
        
        
print("\n=== 🔁 Second Pass Reassignment for Soft-Conflict Courses ===")

for course in conflicted_courses:
    row = course_info[course_info.Course == course].iloc[0]
    ctype = row.Type
    groups = groupwise_df[groupwise_df.Course == course].Group.unique()
    is_mandatory = row.MandatoryGroups > 0
    prev_assignment = course_to_assignment[course]
    
    # Temporarily store assignments for rollback
    backup_assignments = assignments.copy()
    backup_room_occupancy = {slot: {h: set(v) for h, v in halves.items()} for slot, halves in room_occupancy.items()}
    backup_group_occupancy = defaultdict(set, {k: set(v) for k, v in group_occupancy.items()})
    
    # Try normal reassignment
    success = assign_course(course, ctype, groups, priority=False)
    
    # Try forced reassignment with can_preempt
    if not success and is_mandatory:
        success = assign_course(course, ctype, groups, priority=False, can_preempt=True)

    # Last resort: ignore even hard conflicts
    if not success:
        success = assign_course(course, ctype, groups, priority=False, ignore_conflicts=True)

    # === Validation: Keep only if it reduced soft conflict ===
    new_row = next((a for a in assignments if a["Course"] == course), None)
    if new_row:
        slot = new_row["TimeSlot"]
        half = new_row["Half"]
        my_groups = set(groups)

        conflict_found = False
        for other in assignments:
            if other["Course"] == course or other["TimeSlot"] != slot:
                continue
            if not is_conflicting(half, other["Half"]):
                continue
            other_groups = set(groupwise_df[groupwise_df["Course"] == other["Course"]]["Group"])
            if my_groups & other_groups:
                conflict_found = True
                break

        if conflict_found:
            # Roll back
            assignments = backup_assignments
            room_occupancy = backup_room_occupancy
            group_occupancy = backup_group_occupancy
            assignments.append(prev_assignment)
     
        
        
        
print("\n=== 🚨 Hard Conflicts Between Mandatory Courses ===")

from itertools import combinations

# Filter mandatory course assignments
mandatory_assignments = [
    a for a in assignments
    if course_info.loc[course_info.Course == a["Course"], "MandatoryGroups"].values[0] > 0
]

# Track reported conflicts to avoid duplicates
reported_pairs = set()
conflict_report = []

def same_or_overlapping_half(h1, h2):
    return h1 == h2 or "Long" in (h1, h2)

for a1, a2 in combinations(mandatory_assignments, 2):
    if a1["TimeSlot"] != a2["TimeSlot"]:
        continue
    if not same_or_overlapping_half(a1["Half"], a2["Half"]):
        continue

    g1 = set(groupwise_df[(groupwise_df["Course"] == a1["Course"]) &
                          (groupwise_df["GroupTag"] == "mandatory")]["Group"])
    g2 = set(groupwise_df[(groupwise_df["Course"] == a2["Course"]) &
                          (groupwise_df["GroupTag"] == "mandatory")]["Group"])
    shared = g1 & g2
    if shared:
        pair = tuple(sorted((a1["Course"], a2["Course"])))
        if pair not in reported_pairs:
            reported_pairs.add(pair)
            conflict_report.append({
                "Slot": a1["TimeSlot"],
                "RoomA": a1["Room"],
                "HalfA": a1["Half"],
                "RoomB": a2["Room"],
                "HalfB": a2["Half"],
                "CourseA": a1["Course"],
                "CourseB": a2["Course"],
                "Groups": sorted(shared)
            })

# Print results
if not conflict_report:
    print("✅ No conflicts between mandatory courses.")
else:
    for c in conflict_report:
        print(f"\n🕒 {c['Slot']}:")
        print(f"  🔻 {c['CourseA']} ({c['RoomA']}, {c['HalfA']}) ⟷ {c['CourseB']} ({c['RoomB']}, {c['HalfB']})")
        print(f"     • Shared mandatory group(s): {', '.join(c['Groups'])}")
        
    

# === Create Assignment DataFrame ===
assignments_df = pd.DataFrame(assignments)
assignments_df = assignments_df.merge(course_info, on="Course", how="left")
assignments_df = assignments_df.sort_values(by=["TimeSlot", "Half", "Room"])
print("\n=== Final Course Assignments ===")
print(assignments_df[["Course", "TimeSlot", "Room", "Half", "MandatoryGroups", "SoftConflict"]].to_string(index=False))

def is_conflicting(h1, h2):
    return h1 == h2 or "Long" in (h1, h2)

# Build group mapping
group_map = groupwise_df.groupby("Course")["Group"].apply(set).to_dict()

# Recalculate true soft conflicts
def has_soft_conflict(row, all_assignments):
    course = row["Course"]
    slot = row["TimeSlot"]
    half = row["Half"]
    groups = group_map.get(course, set())
    
    for _, other in all_assignments.iterrows():
        if other["Course"] == course:
            continue
        if other["TimeSlot"] != slot:
            continue
        if not is_conflicting(half, other["Half"]):
            continue
        
        other_groups = group_map.get(other["Course"], set())
        if groups & other_groups:
            return True
    return False

# === Clear old SoftConflict values before recomputing ===
assignments_df["SoftConflict"] = False


# Update the column
assignments_df["SoftConflict"] = assignments_df.apply(
    lambda row: has_soft_conflict(row, assignments_df),
    axis=1
)


# === Output diagnostics to screen ===
if unassigned:
    print("\n--- Unassigned Courses ---")
    for c in unassigned:
        print(f"{c}: {diagnostics.get(c, 'No info')}")

# === Create Timetable DataFrame ===
days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
slots = ["AM", "PM"]
timetable = {slot: {day: "" for day in days} for slot in slots}

for _, row in assignments_df.iterrows():
    day, slot = row.TimeSlot.split("_")
    
    # Append H1/H2/Long clearly to the course label
    cell = f"{row.Course} ({row.Room}, {row.Half})"
    if row.SoftConflict:
        cell += " *"
    
    timetable[slot][day] += cell + "\n"

# === Create DataFrame and Save as Excel ===
timetable_df = pd.DataFrame.from_dict(timetable, orient="index")[days]
timetable_df.index.name = "TimeSlot"
timetable_df.to_excel("weekly_timetable_fall2025.xlsx")


# === Evaluation Metrics ===
print("\n=== Diagnostic Metrics ===")

# Total unassigned
print(f"🧩 Unassigned courses: {len(unassigned)}")

# Total soft conflicts
total_soft_conflicts = assignments_df["SoftConflict"].sum()
print(f"🔥 Soft conflicts: {total_soft_conflicts}")

# Merge room capacities for room usage analysis
room_capacity_map = room_df.set_index("Room")["Capacity"].to_dict()
assignments_df["RoomCapacity"] = assignments_df["Room"].map(room_capacity_map)
assignments_df["OverloadPenalty"] = (assignments_df["EstimatedStudents"] - assignments_df["RoomCapacity"]).clip(lower=0)
assignments_df["UnderusePenalty"] = (assignments_df["RoomCapacity"] - assignments_df["EstimatedStudents"]).clip(lower=0)

# Overload penalty
print(f"📈 Total overload penalty (students exceeding room capacity): {assignments_df['OverloadPenalty'].sum()}")

# Underuse (optional)
print(f"📉 Total room underuse (unused capacity): {assignments_df['UnderusePenalty'].sum()}")

# Room utilization efficiency
used_rooms = assignments_df.shape[0]
avg_fill_ratio = (assignments_df["EstimatedStudents"] / assignments_df["RoomCapacity"]).mean()
print(f"🏛️ Average room fill ratio: {avg_fill_ratio:.2f} (based on estimated students)")

# Load distribution across days and halves
day_slot_counts = assignments_df.groupby("TimeSlot").size()
print("\n📅 Time slot utilization:")
for slot in time_slots:
    count = day_slot_counts.get(slot, 0)
    print(f"  {slot}: {count} course(s)")

half_counts = assignments_df.groupby(["TimeSlot", "Half"]).size().unstack(fill_value=0)
print("\n🌓 Half-slot usage per time slot:")
print(half_counts)


print(f"\n📦 Evicted courses attempted to reassign: {len(evicted_courses)}")
print(f"📉 Remaining unassigned courses: {len(unassigned)}")

import colorama
from colorama import Fore, Style
colorama.init(autoreset=True)

print(f"\n{Style.BRIGHT}=== Final Soft Conflict Diagnostics (by slot) ==={Style.RESET_ALL}")

from collections import defaultdict

conflict_by_slot = defaultdict(list)
slot_half_map = defaultdict(list)

# Build slot → course map by half
for _, row in assignments_df.iterrows():
    slot_half_map[(row["TimeSlot"], row["Half"])].append(row["Course"])
    if row["Half"] != "Long":
        slot_half_map[(row["TimeSlot"], "Long")].append(row["Course"])
    if row["Half"] == "Long":
        slot_half_map[(row["TimeSlot"], "H1")].append(row["Course"])
        slot_half_map[(row["TimeSlot"], "H2")].append(row["Course"])

# Build mappings
course_to_groups = {
    c: set(groupwise_df[groupwise_df["Course"] == c]["Group"])
    for c in assignments_df["Course"]
}
course_to_mandatory = {
    c: set(groupwise_df[(groupwise_df["Course"] == c) & 
                        (groupwise_df["GroupTag"] == "mandatory")]["Group"])
    for c in assignments_df["Course"]
}

# Build conflicts
for _, row in assignments_df[assignments_df["SoftConflict"]].iterrows():
    course = row["Course"]
    slot = row["TimeSlot"]
    half = row["Half"]
    room = row["Room"]

    my_groups = course_to_groups.get(course, set())
    my_mandatory = course_to_mandatory.get(course, set())
    regular_groups = my_groups - my_mandatory

    # Conflicting courses in same slot+half (considering Long)
    others = set(slot_half_map[(slot, half)])
    if half != "Long":
        others |= set(slot_half_map[(slot, "Long")])
    else:
        others |= set(slot_half_map[(slot, "H1")]) | set(slot_half_map[(slot, "H2")])
    others.discard(course)

    details = []
    for other in sorted(others):
        other_groups = course_to_groups.get(other, set())
        other_mandatory = course_to_mandatory.get(other, set())

        for g in sorted(regular_groups & other_groups):
            is_mandatory = g in other_mandatory
            detail = f"  {Fore.CYAN}• Group {g}{Style.RESET_ALL} shared with {Fore.YELLOW}{other}{Style.RESET_ALL}"
            if is_mandatory:
                detail += f" {Fore.RED}🚨 (mandatory){Style.RESET_ALL}"
            details.append(detail)

    if details:
        header = f"{Fore.RED}🔻 {Style.BRIGHT}{course}{Style.RESET_ALL} @ {slot} in Room {room} ({half})"
        conflict_by_slot[slot].append((header, details))

# Display by slot
for slot in time_slots:
    if conflict_by_slot[slot]:
        print(f"\n🕒 {Style.BRIGHT}{slot}{Style.RESET_ALL}:")
        for header, details in conflict_by_slot[slot]:
            print(f"  {header}")
            for d in details:
                print(f"   {d}")
                
                

                
# Recalculate soft conflicts manually
manual_soft_conflicts = 0

for i, row_i in assignments_df.iterrows():
    course_i = row_i["Course"]
    slot_i = row_i["TimeSlot"]
    half_i = row_i["Half"]
    groups_i = set(groupwise_df[groupwise_df["Course"] == course_i]["Group"])
    
    # Expand half: Long overlaps with H1 and H2
    halves_to_check = {"Long"} if half_i == "Long" else {half_i, "Long"}
    
    for j, row_j in assignments_df.iterrows():
        if i == j:
            continue
        if row_j["TimeSlot"] != slot_i:
            continue
        if row_j["Half"] not in halves_to_check:
            continue
        
        course_j = row_j["Course"]
        groups_j = set(groupwise_df[groupwise_df["Course"] == course_j]["Group"])
        if groups_i & groups_j:
            manual_soft_conflicts += 1
            break  # count this course only once


print("SoftConflict column sum:", total_soft_conflicts)
print("Manually recomputed soft conflicts:", manual_soft_conflicts)

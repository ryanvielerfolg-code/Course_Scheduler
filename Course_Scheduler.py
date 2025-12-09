# Course Scheduler for Fall 2025 — Final Optimized Greedy Algorithm
# Fixes: Room Occupancy, Load Balancing (Spread), JSON Serialization, L/S Logic

import math
import pandas as pd
import numpy as np
from collections import defaultdict
from openpyxl.styles import Alignment
import os

# === 1. Setup & Configuration ===

# Define Rooms and Capacities
room_df = pd.DataFrame({
    "Room": ["Amphitheater", "101", "102", "151", "152", "153", "154", "155", "10", "12"],
    "Capacity": [201, 95, 49, 90, 48, 48, 16, 16, 18, 15]
})

# Define Time Slots (Mon-Fri, AM/PM)
time_slots = [
    "Mon_AM", "Mon_PM",
    "Tue_AM", "Tue_PM",
    "Wed_AM", "Wed_PM",
    "Thu_AM", "Thu_PM",
    "Fri_AM", "Fri_PM",
]

# === 2. Data Loading & Cleaning Functions ===

def load_groupwise(path: str) -> pd.DataFrame:
    """Load course metadata (Track, Type, Mandatory/Regular)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")
        
    df = pd.read_excel(path)
    # Filter and clean
    cols = ["Course", "Track", "GroupTag", "Type"]
    # Ensure columns exist
    missing = [c for c in cols if c not in df.columns]
    if missing:
        # Fallback for simple template matching if strict columns missing
        pass 
        
    df = df.dropna(subset=cols)
    df["Course"] = df["Course"].astype(str).str.strip()
    df["Track"] = df["Track"].astype(str).str.strip()
    df["GroupTag"] = df["GroupTag"].astype(str).str.strip().str.lower()
    df["Type"] = df["Type"].astype(str).str.strip().str.upper()
    
    # Normalize values
    df.loc[~df["GroupTag"].isin(["mandatory", "regular"]), "GroupTag"] = "regular"
    df.loc[~df["Type"].isin(["L", "S"]), "Type"] = "S" # Default to Short if unknown
    return df

def load_students(path: str) -> pd.DataFrame:
    """Load student counts."""
    if not os.path.exists(path):
        print(f"⚠️ Warning: {path} not found. Using dummy data.")
        return pd.DataFrame(columns=["Course", "Students_2024"])
        
    df = pd.read_csv(path)
    
    # Basic cleaning to find the right columns
    course_col = next((c for c in df.columns if "course" in c.lower()), df.columns[0])
    student_col = next((c for c in df.columns if "student" in c.lower()), df.columns[1])
    
    df = df[[course_col, student_col]].copy()
    df.columns = ["Course", "Students_2024"]
    
    df["Course"] = df["Course"].astype(str).str.strip()
    df["Students_2024"] = pd.to_numeric(df["Students_2024"], errors="coerce").fillna(0).astype(int)
    return df

# === 3. Pre-processing ===

print("--- Loading Data ---")
try:
    groupwise_df = load_groupwise("groupwise_course_tags_fall2025.xlsx")
    students_df = load_students("number-of-students-fall-2024-extracted.csv")
except Exception as e:
    print(f"Error loading files: {e}")
    # Initialize empty defaults to prevent crash
    course_info = pd.DataFrame()
    exit(1)

# Aggregating Course Info
def get_primary_value(series):
    return series.mode()[0] if not series.mode().empty else series.iloc[0]

course_info = groupwise_df.groupby("Course").agg(
    Track=("Track", get_primary_value),
    Type=("Type", get_primary_value),
    IsMandatory=("GroupTag", lambda s: (s == "mandatory").any())
).reset_index()

# Merge Student Counts
course_info = course_info.merge(students_df, on="Course", how="left")
course_info["Students_2024"] = course_info["Students_2024"].fillna(0).astype(int)

# === GREEDY STRATEGY: SORTING ===
# Priority: Mandatory -> High Enrollment -> Long Duration
course_info = course_info.sort_values(
    by=["IsMandatory", "Students_2024", "Type"],
    ascending=[False, False, True] 
).reset_index(drop=True)

print(f"Loaded {len(course_info)} unique courses to schedule.")

# === 4. Scheduler State Initialization ===

assignments = []
unassigned = []

# Slot Load (for soft balancing)
slot_load = {slot: 0 for slot in time_slots}

# Track Constraints: Track -> Set of (Slot, Half)
track_mandatory_usage = defaultdict(set) 

# Room Occupancy: (Slot, Room) -> Set of Halves {'H1', 'H2'}
room_occupancy = defaultdict(set)

def is_room_free(slot, room, required_halves):
    """Check if the room is free for the required halves in the given slot."""
    occupied_halves = room_occupancy.get((slot, room), set())
    if not required_halves.isdisjoint(occupied_halves):
        return False
    return True

def book_room(slot, room, halves):
    """Mark room as occupied."""
    current = room_occupancy[(slot, room)]
    room_occupancy[(slot, room)] = current.union(halves)

def check_track_conflict(track, slot, halves):
    """Check if this track already has a mandatory class in this slot/half."""
    used_halves = track_mandatory_usage.get((track, slot), set())
    if not halves.isdisjoint(used_halves):
        return True 
    return False

def record_track_usage(track, slot, halves):
    current = track_mandatory_usage[(track, slot)]
    track_mandatory_usage[(track, slot)] = current.union(halves)


# === 5. Main Greedy Loop ===

print("\n--- Starting Greedy Schedule ---")

for _, row in course_info.iterrows():
    course = row["Course"]
    track = row["Track"]
    is_mandatory = row["IsMandatory"]
    students = row["Students_2024"]
    ctype = row["Type"] 

    # Prepare required halves
    if ctype == 'L':
        possible_half_configs = [{'H1', 'H2'}]
    else:
        # Prefer H1, but allow H2
        possible_half_configs = [{'H1'}, {'H2'}]

    best_choice = None
    best_score = float('inf')

    # Iterate all Time Slots
    for slot in time_slots:
        
        # Iterate all Half Configurations
        for required_halves in possible_half_configs:
            
            # --- Hard Constraint 1: Mandatory Track Conflict ---
            if is_mandatory:
                if check_track_conflict(track, slot, required_halves):
                    continue 

            # --- Hard Constraint 2 & Soft Constraint (Best Fit) ---
            # Filter rooms by capacity
            valid_rooms = room_df[room_df["Capacity"] >= students].copy()
            # Sort valid rooms by Capacity ASCENDING (Best Fit Strategy)
            valid_rooms = valid_rooms.sort_values(by="Capacity", ascending=True)
            
            selected_room = None
            selected_capacity = 0
            
            # Find first available room
            for _, r_data in valid_rooms.iterrows():
                r_name = r_data["Room"]
                r_cap = r_data["Capacity"]
                
                if is_room_free(slot, r_name, required_halves):
                    selected_room = r_name
                    selected_capacity = r_cap
                    break 
            
            if not selected_room:
                continue 
            
            # --- Soft Constraints Calculation (Scoring) ---
            
            # 1. Load Balance (SPREAD): 
            # Use simple load count. Less load = Better score.
            load_penalty = slot_load[slot]
            
            # 2. Track Overlap (Regular)
            overlap_penalty = 0
            if not is_mandatory:
                for a in assignments:
                    if a["TimeSlot"] == slot and a["Track"] == track:
                        if not required_halves.isdisjoint(a["Halves"]):
                            overlap_penalty = 1
                            break
            
            # 3. Room Slack (Waste)
            slack_penalty = (selected_capacity - students) / 10.0 
            
            # Total Score (Weighted)
            # High weight on overlap to prevent it
            # Moderate weight on load to force spreading across week
            total_score = (load_penalty * 10) + (overlap_penalty * 100) + slack_penalty
            
            if total_score < best_score:
                best_score = total_score
                half_str = "Long" if ctype == 'L' else list(required_halves)[0]
                
                best_choice = {
                    "Course": course,
                    "TimeSlot": slot,
                    "Room": selected_room,
                    "Half": half_str,
                    "Halves": required_halves,
                    "Track": track,
                    "IsMandatory": is_mandatory,
                    "Students": students,
                    "Capacity": selected_capacity,
                    "Score": best_score
                }

    # Assign the best found slot
    if best_choice:
        assignments.append(best_choice)
        slot_load[best_choice["TimeSlot"]] += 1
        book_room(best_choice["TimeSlot"], best_choice["Room"], best_choice["Halves"])
        if is_mandatory:
            record_track_usage(track, best_choice["TimeSlot"], best_choice["Halves"])
    else:
        unassigned.append({
            "Course": course,
            "Reason": "No valid room/slot found"
        })

# === 6. Output & Diagnostics ===

print("\n--- Scheduling Complete ---")
if unassigned:
    print(f"⚠️ Warning: {len(unassigned)} courses could not be scheduled:")
else:
    print("✅ All courses successfully scheduled!")

# Initialize variables
days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
slots = ["AM", "PM"]
timetable = {s: {d: "" for d in days} for s in slots}

# Build DataFrame
if not assignments:
    assignments_df = pd.DataFrame(columns=["Course", "TimeSlot", "Room", "Half", "Track", "IsMandatory", "Students", "Capacity", "SoftConflict"])
else:
    assignments_df = pd.DataFrame(assignments)

if not assignments_df.empty:
    # Recalculate Soft Conflicts
    def check_soft_conflict(row):
        if row["IsMandatory"]: return False
        current_halves = row["Halves"]
        others = assignments_df[
            (assignments_df["TimeSlot"] == row["TimeSlot"]) & 
            (assignments_df["Track"] == row["Track"]) & 
            (assignments_df["Course"] != row["Course"])
        ]
        for _, o in others.iterrows():
            if not current_halves.isdisjoint(o["Halves"]):
                return True
        return False

    assignments_df["SoftConflict"] = assignments_df.apply(check_soft_conflict, axis=1)
    
    # Data Cleaning for JSON/Web
    safe_cols = ["Course", "TimeSlot", "Room", "Half", "Track", "IsMandatory", "Students", "Capacity", "SoftConflict"]
    assignments_df = assignments_df[safe_cols].copy()
    
    assignments_df["Students"] = assignments_df["Students"].astype(int)
    assignments_df["Capacity"] = assignments_df["Capacity"].astype(int)
    assignments_df["SoftConflict"] = assignments_df["SoftConflict"].astype(bool)
    assignments_df["IsMandatory"] = assignments_df["IsMandatory"].astype(bool)
    
    assignments_df = assignments_df.sort_values(by=["TimeSlot", "Room"])
    
    print("\nTop 10 Assignments:")
    print(assignments_df.head(10).to_string(index=False))
    
    # Fill Master Timetable Dictionary
    for _, row in assignments_df.iterrows():
        day, period = row["TimeSlot"].split("_")
        entry = f"{row['Course']} ({row['Room']}, {row['Half']})"
        if row["SoftConflict"]:
            entry += " *"
        current = timetable[period][day]
        timetable[period][day] = (current + "\n" + entry) if current else entry
            
    # === NEW: Save Excel with Formatting (Spacing & Alignment) ===
    output_filename = "weekly_timetable_fall2025.xlsx"
    
    # 定义一个格式化函数，专门用来把表格变“漂亮”
    def format_worksheet(worksheet):
        # 1. 设置列宽 (设为 30，足够宽以容纳课程信息)
        for col in ['A', 'B', 'C', 'D', 'E', 'F']:
            worksheet.column_dimensions[col].width = 35

        # 2. 遍历每一行，设置自动换行、居中和动态行高
        for row in worksheet.iter_rows():
            max_lines = 1
            for cell in row:
                # 设置对齐方式：自动换行，水平居中，垂直居中
                cell.alignment = Alignment(wrap_text=True, horizontal='center', vertical='center')
                
                # 计算这个格子里有多少行文字（根据换行符 \n）
                if cell.value and isinstance(cell.value, str):
                    lines = str(cell.value).count('\n') + 1
                    if lines > max_lines:
                        max_lines = lines
            
            # 3. 设置行高
            # 这里的逻辑是：每一行文字给 25 的高度，基础再加 10 的边距
            # 这样即使只有一行字，也不会贴着边框
            current_row_idx = row[0].row
            if current_row_idx == 1:
                # 表头稍微高一点
                worksheet.row_dimensions[current_row_idx].height = 40
            else:
                # 内容行高度 = 行数 * 25 + 10 (Padding)
                worksheet.row_dimensions[current_row_idx].height = (max_lines * 25) + 10

    try:
        # 使用 openpyxl 引擎写入
        with pd.ExcelWriter(output_filename, engine='openpyxl') as writer:
            
            # --- Sheet 1: Master Schedule ---
            timetable_df = pd.DataFrame.from_dict(timetable, orient="index")[days]
            timetable_df.index.name = "TimeSlot"
            timetable_df.to_excel(writer, sheet_name="Master_Schedule")
            
            # 对 Master Schedule 应用格式
            format_worksheet(writer.sheets["Master_Schedule"])
            
            # --- Sheet 2~N: Individual Track Schedules ---
            all_tracks = sorted(groupwise_df['Track'].unique())
            
            for track in all_tracks:
                sheet_name = "".join(c for c in str(track) if c.isalnum() or c in (' ', '_', '-'))[:30]
                
                track_courses = groupwise_df[groupwise_df['Track'] == track]['Course'].unique()
                track_assignments = assignments_df[assignments_df['Course'].isin(track_courses)]
                
                if track_assignments.empty:
                    continue
                    
                track_timetable = {s: {d: "" for d in days} for s in slots}
                
                for _, row in track_assignments.iterrows():
                    day, period = row["TimeSlot"].split("_")
                    course_name = row['Course']
                    
                    tags = groupwise_df[
                        (groupwise_df['Course'] == course_name) & 
                        (groupwise_df['Track'] == track)
                    ]['GroupTag']
                    
                    tag_label = ""
                    if not tags.empty:
                        tag_type = tags.iloc[0].lower()
                        if 'mandatory' in tag_type:
                            tag_label = " [M]"
                        else:
                            tag_label = " [R]"
                    
                    entry = f"{course_name}{tag_label}\n({row['Room']})" # 这里加了 \n 让教室名换行显示，更整洁
                    
                    current = track_timetable[period][day]
                    track_timetable[period][day] = (current + "\n\n" + entry) if current else entry # 课程之间加两个换行
                
                track_df = pd.DataFrame.from_dict(track_timetable, orient="index")[days]
                track_df.index.name = "TimeSlot"
                track_df.to_excel(writer, sheet_name=sheet_name)
                
                # 对 Track Sheet 应用格式
                format_worksheet(writer.sheets[sheet_name])
                
        print(f"\n📁 Timetable saved with FORMATTING to: {output_filename}")
        
    except Exception as e:
        print(f"Error saving Excel: {e}")
        # Fallback
        timetable_df = pd.DataFrame.from_dict(timetable, orient="index")[days]
        timetable_df.to_excel("weekly_timetable_fall2025.xlsx")

else:
    print("No assignments made.")
    timetable_df = pd.DataFrame.from_dict(timetable, orient="index")[days]
    timetable_df.to_excel("weekly_timetable_fall2025.xlsx")

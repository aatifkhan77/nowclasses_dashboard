import streamlit as st
import pandas as pd
import numpy as np
import glob
import os
from datetime import date as date_cls

# ------------------------------
# Streamlit Page Configuration
# ------------------------------
st.set_page_config(
    page_title="Student Attendance Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Student Attendance Dashboard")

st.markdown(
    """
This dashboard is built for **student-wise, subject-wise, and teacher-wise attendance analysis**.

- Use the filters in the sidebar to slice the data.
"""
)

# ------------------------------
# Data Loading with Caching
# ------------------------------
@st.cache_data
def load_data(attendance_path: str, student_master_path: str):
    """Load and preprocess attendance + master data."""
    # Read Excel files
    attendance = pd.read_excel(attendance_path)
    students = pd.read_excel(student_master_path)

    # Basic cleaning / type conversion
    attendance["Date"] = pd.to_datetime(attendance["Date"], errors="coerce")
    attendance = attendance.dropna(subset=["Date"])  # ensure valid dates

    attendance["Duration_Minutes"] = (
        attendance["Duration_Minutes"].fillna(0).astype(float)
    )
    attendance["Duration_Hours"] = attendance["Duration_Minutes"] / 60.0

    # Merge with master on student name (best-effort)
    # In your master: Name, Grade, Email, Status
    merged = attendance.merge(
        students[["Student_ID", "Name", "Grade", "Email", "Status"]],
        left_on="Student_Name",
        right_on="Name",
        how="left",
    )

    # Rename merged name column to avoid confusion
    merged = merged.rename(columns={"Name": "Student_Name_Master"})

    return merged, students


# ------------------------------
# Sidebar: File Paths & Load Data
# ------------------------------
st.sidebar.header("📁 Data Files")

# Auto-detect attendance files in current folder
attendance_files = glob.glob("*attendance_master*.xlsx")

if not attendance_files:
    st.sidebar.error(
        "No attendance file found matching `*attendance_master*.xlsx` in this folder.\n\n"
        "Place your attendance file (e.g. `attendance_master_normalized_november.xlsx`) "
        "in the same folder as this script."
    )
    st.stop()

# Sort by modified time (oldest → newest)
attendance_files = sorted(attendance_files, key=os.path.getmtime)

# Default: latest file
default_index = len(attendance_files) - 1

attendance_path = st.sidebar.selectbox(
    "Select attendance file",
    options=attendance_files,
    index=default_index,
    help="All files matching *attendance_master*.xlsx in this folder",
)

# Student/teacher master stays fixed (but can be changed if needed)
student_master_path = st.sidebar.text_input(
    "Student master file path",
    value="nowclasses_final_master.xlsx",
    help="Master file for students/teachers (remains same)",
)

data_loaded = False
df = None
students_master = None

if attendance_path and student_master_path:
    try:
        df, students_master = load_data(attendance_path, student_master_path)
        data_loaded = True
    except FileNotFoundError as e:
        st.error(f"❌ File not found: {e}")
    except Exception as e:
        st.error(f"❌ Error loading files: {e}")

if not data_loaded or df is None or df.empty:
    st.error("No valid data loaded from the selected files.")
    st.stop()

# ------------------------------
# Sidebar: Filters
# ------------------------------
st.sidebar.header("🔍 Filters")

# Ensure no missing dates
df = df.dropna(subset=["Date"])

if df.empty:
    st.error("No valid rows with dates found in attendance file.")
    st.stop()

# Student filter
student_list = sorted(df["Student_Name"].dropna().unique().tolist())
selected_students = st.sidebar.multiselect(
    "Select student(s)",
    options=student_list,
    default=[],
    help="Leave empty to include all students",
)

# Subject filter
subject_list = sorted(df["Subject"].dropna().unique().tolist())
selected_subjects = st.sidebar.multiselect(
    "Select subject(s)",
    options=subject_list,
    default=[],
    help="Leave empty to include all subjects",
)

# Teacher filter
teacher_list = sorted(df["Teacher_Name"].dropna().unique().tolist())
selected_teachers = st.sidebar.multiselect(
    "Select teacher(s)",
    options=teacher_list,
    default=[],
    help="Leave empty to include all teachers",
)

# ------------------------------
# Date range filter – dynamic from file
# ------------------------------
min_date = df["Date"].min().date()
max_date = df["Date"].max().date()

# Safety: ensure min_date <= max_date
if min_date > max_date:
    min_date, max_date = max_date, min_date

date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
    help="Filter attendance between these dates",
    key=f"date_range_{attendance_path}",  # reset when file changes
)

# Normalize date_range into start_date, end_date
if isinstance(date_range, (list, tuple)):
    if len(date_range) == 0:
        start_date = min_date
        end_date = max_date
    elif len(date_range) == 1:
        start_date = date_range[0]
        end_date = date_range[0]
    else:
        start_date, end_date = date_range[0], date_range[1]
else:
    # Single date selected
    start_date = date_range
    end_date = date_range

# Ensure they are date objects
if isinstance(start_date, pd.Timestamp):
    start_date = start_date.date()
if isinstance(end_date, pd.Timestamp):
    end_date = end_date.date()

# Safety: swap if user selects in wrong order
if start_date > end_date:
    start_date, end_date = end_date, start_date

# ------------------------------
# Apply Filters
# ------------------------------
filtered_df = df.copy()

# Student filter
if selected_students:
    filtered_df = filtered_df[filtered_df["Student_Name"].isin(selected_students)]

# Subject filter
if selected_subjects:
    filtered_df = filtered_df[filtered_df["Subject"].isin(selected_subjects)]

# Teacher filter
if selected_teachers:
    filtered_df = filtered_df[filtered_df["Teacher_Name"].isin(selected_teachers)]

# Date range filter
filtered_df = filtered_df[
    (filtered_df["Date"].dt.date >= start_date)
    & (filtered_df["Date"].dt.date <= end_date)
]

if filtered_df.empty:
    st.warning(
        f"No data found for the selected filters.\n\n"
        f"Attendance file: `{attendance_path}`\n"
        f"Date range: {start_date} → {end_date}"
    )
    st.stop()

# ------------------------------
# Top Summary Metrics
# ------------------------------
st.subheader("📌 Overview (Filtered Data)")

total_duration_hours = filtered_df["Duration_Hours"].sum()
total_duration_minutes = filtered_df["Duration_Minutes"].sum()
unique_students = filtered_df["Student_Name"].nunique()
unique_subjects = filtered_df["Subject"].nunique()
unique_teachers = filtered_df["Teacher_Name"].nunique()
unique_dates = filtered_df["Date"].dt.normalize().nunique()
total_records = len(filtered_df)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Duration (hours)", f"{total_duration_hours:.1f}")
c2.metric("Total Duration (minutes)", f"{total_duration_minutes:.0f}")
c3.metric("Unique Students", unique_students)
c4.metric("Unique Dates", unique_dates)

c5, c6, c7 = st.columns(3)
c5.metric("Subjects", unique_subjects)
c6.metric("Teachers", unique_teachers)
c7.metric("Attendance Records", total_records)

st.markdown("---")

# ------------------------------
# Student-wise Summary
# ------------------------------
st.subheader("🧑‍🎓 Student-wise Attendance Summary")

student_summary = (
    filtered_df.groupby("Student_Name")
    .agg(
        Total_Duration_Minutes=("Duration_Minutes", "sum"),
        Total_Duration_Hours=("Duration_Hours", "sum"),
        Sessions=("Date", "count"),
        First_Date=("Date", "min"),
        Last_Date=("Date", "max"),
    )
    .reset_index()
    .sort_values("Total_Duration_Hours", ascending=False)
)

student_summary["First_Date"] = student_summary["First_Date"].dt.date
student_summary["Last_Date"] = student_summary["Last_Date"].dt.date

st.dataframe(student_summary, use_container_width=True)

if not student_summary.empty:
    st.bar_chart(
        data=student_summary.set_index("Student_Name")["Total_Duration_Hours"],
        use_container_width=True,
    )

st.markdown("---")

# ------------------------------
# Teacher-wise & Subject-wise Summary
# ------------------------------
c_left, c_right = st.columns(2)

with c_left:
    st.subheader("👨‍🏫 Teacher-wise Summary")
    teacher_summary = (
        filtered_df.groupby("Teacher_Name")
        .agg(
            Total_Duration_Hours=("Duration_Hours", "sum"),
            Sessions=("Date", "count"),
            Unique_Students=("Student_Name", "nunique"),
        )
        .reset_index()
        .sort_values("Total_Duration_Hours", ascending=False)
    )
    st.dataframe(teacher_summary, use_container_width=True)
    if not teacher_summary.empty:
        st.bar_chart(
            data=teacher_summary.set_index("Teacher_Name")["Total_Duration_Hours"],
            use_container_width=True,
        )

with c_right:
    st.subheader("📚 Subject-wise Summary")
    subject_summary_all = (
        filtered_df.groupby("Subject")
        .agg(
            Total_Duration_Hours=("Duration_Hours", "sum"),
            Sessions=("Date", "count"),
            Unique_Students=("Student_Name", "nunique"),
        )
        .reset_index()
        .sort_values("Total_Duration_Hours", ascending=False)
    )
    st.dataframe(subject_summary_all, use_container_width=True)
    if not subject_summary_all.empty:
        st.bar_chart(
            data=subject_summary_all.set_index("Subject")["Total_Duration_Hours"],
            use_container_width=True,
        )

st.markdown("---")

# ------------------------------
# Detailed View for a Single Student
# ------------------------------
st.subheader("🔎 Detailed View: Student-wise, Subject-wise, Date-wise")

if len(selected_students) == 1:
    selected_student = selected_students[0]
    st.markdown(f"### 🎓 Detailed Attendance for: **{selected_student}**")

    student_df = filtered_df[filtered_df["Student_Name"] == selected_student]

    # Subject-wise breakdown for this student
    st.markdown("#### 📚 Subject-wise Breakdown")
    student_subject_summary = (
        student_df.groupby("Subject")
        .agg(
            Total_Duration_Hours=("Duration_Hours", "sum"),
            Sessions=("Date", "count"),
            Unique_Dates=("Date", lambda x: x.dt.normalize().nunique()),
        )
        .reset_index()
        .sort_values("Total_Duration_Hours", ascending=False)
    )

    st.dataframe(student_subject_summary, use_container_width=True)

    if not student_subject_summary.empty:
        st.bar_chart(
            data=student_subject_summary.set_index("Subject")["Total_Duration_Hours"],
            use_container_width=True,
        )

    # Date-wise breakdown (total duration per date)
    st.markdown("#### 🗓️ Date-wise Total Duration")
    daily_summary = (
        student_df.groupby(student_df["Date"].dt.date)
        .agg(Total_Duration_Hours=("Duration_Hours", "sum"))
        .reset_index()
        .rename(columns={"Date": "Session_Date"})
    )

    st.dataframe(daily_summary, use_container_width=True)

    if not daily_summary.empty:
        st.line_chart(
            data=daily_summary.set_index("Session_Date")["Total_Duration_Hours"],
            use_container_width=True,
        )

    # Date x Subject table: which dates, which subject, how long
    st.markdown("#### 🗓️📚 Date & Subject-wise Attendance (Table)")
    date_subject_pivot = (
        student_df.assign(DateOnly=student_df["Date"].dt.date)
        .pivot_table(
            index="DateOnly",
            columns="Subject",
            values="Duration_Hours",
            aggfunc="sum",
            fill_value=0,
        )
    )

    st.dataframe(date_subject_pivot, use_container_width=True)

else:
    st.info(
        "Select **exactly one student** in the sidebar to see detailed subject-wise and date-wise breakdown."
    )

st.markdown("---")

# ------------------------------
# Raw Filtered Data Table
# ------------------------------
st.subheader("📄 Raw Attendance Records (Filtered)")

show_source = st.checkbox("Show Source_File column", value=False)

display_cols = [
    "Date",
    "Student_Name",
    "Teacher_Name",
    "Subject",
    "Duration_Minutes",
    "Duration_Hours",
]

if show_source and "Source_File" in filtered_df.columns:
    display_cols.append("Source_File")

raw_table = filtered_df[display_cols].sort_values(["Date", "Student_Name"])

st.dataframe(raw_table, use_container_width=True)


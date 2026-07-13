import streamlit as st
import pandas as pd
import sqlite3
import io
import re

# --- DATABASE MANAGEMENT FUNCTIONS ---
def get_db_connection():
    conn = sqlite3.connect("motors.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS motor_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT,
            equipment TEXT,
            drive TEXT,
            matcode REAL,
            qty TEXT,
            kw_hp REAL,
            rpm INTEGER,
            frame TEXT,
            mount TEXT,
            current REAL,
            no_load_current TEXT,
            coupling TEXT,
            status TEXT DEFAULT 'Healthy',
            remarks TEXT
        )
    """)
    conn.commit()
    conn.close()

def load_motor_data():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM motor_registry", conn)
    conn.close()
    return df

def insert_motor(data_tuple):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO motor_registry (area, equipment, drive, matcode, qty, kw_hp, rpm, frame, mount, current, no_load_current, coupling, status, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data_tuple)
    conn.commit()
    conn.close()

def update_motor_status(motor_id, field_name, new_value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE motor_registry SET {field_name} = ? WHERE id = ?", (new_value, motor_id))
    conn.commit()
    conn.close()

def convert_df_to_excel(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        export_df = df.copy()
        if "selector_label" in export_df.columns:
            export_df = export_df.drop(columns=["selector_label"])
        export_df.to_excel(writer, index=False, sheet_name='Motor Registry')
    return buffer.getvalue()

# --- DATA CLEANING & CONSTRAINT UTILITIES ---
def clean_to_numeric_string(val):
    if pd.isna(val) or val is None:
        return ""
    cleaned = re.sub(r'[^0-9.]', '', str(val))
    if cleaned.count('.') > 1:
        parts = cleaned.split('.')
        cleaned = parts + '.' + ''.join(parts[1:])
    return cleaned

def enforce_float_limit(val, max_digits):
    cleaned_str = clean_to_numeric_string(val)
    if not cleaned_str or cleaned_str == ".":
        return None
    no_dot = cleaned_str.replace('.', '')[:max_digits]
    if '.' in cleaned_str:
        dot_idx = cleaned_str.index('.')
        integer_part = cleaned_str[:dot_idx][:max_digits]
        decimal_part = cleaned_str[dot_idx+1:][:(max_digits - len(integer_part))]
        final_str = f"{integer_part}.{decimal_part}".strip('.')
    else:
        final_str = no_dot
    try:
        return float(final_str) if final_str else None
    except ValueError:
        return None

def enforce_int_limit(val, max_digits):
    cleaned_str = clean_to_numeric_string(val)
    clean_int_str = cleaned_str.split('.')[:max_digits]
    try:
        return int(clean_int_str) if clean_int_str else None
    except ValueError:
        return None

def safe_decimal_formatter(val):
    if pd.isna(val) or val is None or str(val).strip().lower() in ['nan', 'none', '']:
        return ""
    try:
        numeric_value = float(val)
        return f"{numeric_value:.2f}"
    except (ValueError, TypeError):
        return str(val)

# --- APP LAYOUT CONFIGURATION ---
st.set_page_config(page_title="Motor Database Manager", layout="wide")
init_database()
df_motors = load_motor_data()

st.title("⚡ Industrial Motor Registry & Tracker")
st.markdown("Designed for rapid on-site mobile asset logging and operational verification.")

tab_view, tab_update, tab_master = st.tabs(["🔍 Search & View", "⚙️ Field Status Update", "🏗️ Master Data Entry"])

# ==================== TAB 1: EASY SEARCH & VIEW ====================
with tab_view:
    export_col1, export_col2 = st.columns(2)
    with export_col1:
        st.subheader("Quick Search Filter")
    with export_col2:
        excel_data = convert_df_to_excel(df_motors)
        st.download_button(
            label="📥 Export to Excel",
            data=excel_data,
            file_name="motor_registry_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    search_col1, search_col2, search_col3, search_col4 = st.columns(4)
    with search_col1:
        area_filter = st.selectbox("Filter by Area / Zone:", ["All"] + sorted(list(df_motors["area"].dropna().unique())) if not df_motors.empty else ["All"])
    with search_col2:
        equipment_filter = st.selectbox("Filter by Equipment Type:", ["All"] + sorted(list(df_motors["equipment"].dropna().unique())) if not df_motors.empty else ["All"])
    with search_col3:
        status_options = ["All", "Healthy", "Under Observation", "Under Maintenance", "Breakdown", "Spare/Scrapped"]
        status_filter = st.selectbox("Filter by Status:", status_options)
    with search_col4:
        search_query = st.text_input("🔍 Keyword Search (Drive, Frame, Matcode):", "").lower()
        
    filtered_df = df_motors.copy()
    if not filtered_df.empty:
        if area_filter != "All":
            filtered_df = filtered_df[filtered_df["area"] == area_filter]
        if equipment_filter != "All":
            filtered_df = filtered_df[filtered_df["equipment"] == equipment_filter]
        if status_filter != "All":
            filtered_df = filtered_df[filtered_df["status"] == status_filter]
        if search_query:
            filtered_df = filtered_df[
                filtered_df["drive"].str.lower().str.contains(search_query, na=False) |
                filtered_df["frame"].str.lower().str.contains(search_query, na=False) |
                filtered_df["matcode"].astype(str).str.lower().str.contains(search_query, na=False)
            ]
        
    st.markdown(f"**Showing {len(filtered_df)} Matching Motors**")
    
    def highlight_status_column(series):
        if series.name == 'status':
            styles = []
            for val in series:
                status = str(val).strip()
                if status == 'Healthy':
                    styles.append('background-color: #d4edda; color: #155724;')
                elif status == 'Under Observation':
                    styles.append('background-color: #d1ecf1; color: #0c5460;')
                elif status == 'Under Maintenance':
                    styles.append('background-color: #fff3cd; color: #856404;')
                elif status == 'Breakdown':
                    styles.append('background-color: #f8d7da; color: #721c24; font-weight: bold;')
                elif status == 'Spare/Scrapped':
                    styles.append('background-color: #e2e3e5; color: #383d41;')
                else:
                    styles.append('')
            return styles
        return [''] * len(series)
        
    if not filtered_df.empty:
        display_cols = ["id", "area", "equipment", "drive", "matcode", "qty", "kw_hp", "rpm", "frame", "mount", "current", "no_load_current", "coupling", "status", "remarks"]
        
        formatted_styled_df = (
            filtered_df[display_cols]
            .style.apply(highlight_status_column, axis=0)
            .format({
                "matcode": safe_decimal_formatter,
                "kw_hp": safe_decimal_formatter,
                "current": safe_decimal_formatter
            })
        )
        st.dataframe(formatted_styled_df, use_container_width=True, hide_index=True)
    else:
        st.info("No records found in database registry matching your active filters.")

# ==================== TAB 2: FIELD STATUS UPDATE ====================
with tab_update:
    st.subheader("Append / Edit Status & Remarks")
    if df_motors.empty:
        st.warning("Please populate the Master Data Registry first via Tab 3.")
    else:
        df_motors["selector_label"] = "ID " + df_motors["id"].astype(str) + " | Loc: " + df_motors["area"].astype(str) + " | " + df_motors["equipment"].astype(str) + " (" + df_motors["drive"].astype(str) + ")"
        selected_motor_label = st.selectbox("Select Target Motor to Modify:", df_motors["selector_label"].tolist())
        
        matched_rows = df_motors[df_motors["selector_label"] == selected_motor_label]
        if not matched_rows.empty:
            # FIX: Added [0] row positioning indicator to prevent inner compilation crash loops
            selected_row = matched_rows.iloc[0]
            m_id = int(selected_row["id"])
            m_area = str(selected_row["area"])
            m_eq = str(selected_row["equipment"])
            m_drv = str(selected_row["drive"])
            m_status = str(selected_row["status"])
            m_remarks = str(selected_row["remarks"])
            
            st.info(f"📍 Modifying: Area {m_area} -> {m_eq} ({m_drv})")
            
            with st.form("status_update_form"):
                current_status = m_status if m_status and m_status != "None" and m_status != "" else "Healthy"
                status_options_edit = ["Healthy", "Under Observation", "Under Maintenance", "Breakdown", "Spare/Scrapped"]
                status_idx = status_options_edit.index(current_status) if current_status in status_options_edit else 0
                
                new_status = st.selectbox("Operational Status:", status_options_edit, index=status_idx)
                current_remarks = m_remarks if m_remarks and m_remarks != "None" else ""
                new_remarks = st.text_area("Field Remarks / Update Log:", value=current_remarks)
                
                submit_status = st.form_submit_button("Submit Operational Status Change")
                
            if submit_status:
                update_motor_status(m_id, "status", new_status)

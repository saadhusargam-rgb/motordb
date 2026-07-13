import streamlit as st
import pandas as pd
import sqlite3

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
            equipment TEXT,
            drive TEXT,
            matcode TEXT,
            qty INTEGER DEFAULT 1,
            kw_hp REAL,
            rpm INTEGER,
            frame TEXT,
            mount TEXT,
            current REAL,
            no_load_current REAL,
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
        INSERT INTO motor_registry (equipment, drive, matcode, qty, kw_hp, rpm, frame, mount, current, no_load_current, coupling, status, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data_tuple)
    conn.commit()
    conn.close()

def update_motor_status(motor_id, field_name, new_value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE motor_registry SET {field_name} = ? WHERE id = ?", (new_value, motor_id))
    conn.commit()
    conn.close()

# --- APP LAYOUT CONFIGURATION ---
st.set_page_config(page_title="Motor Database Manager", layout="wide")
init_database()
df_motors = load_motor_data()

st.title("⚡ Industrial Motor Registry & Tracker")
st.markdown("Designed for rapid on-site mobile asset logging and operational verification.")

tab_view, tab_update, tab_master = st.tabs(["🔍 Search & View", "⚙️ Field Status Update", "🏗️ Master Data Entry"])

# ==================== TAB 1: EASY SEARCH & VIEW ====================
with tab_view:
    st.subheader("Quick Search Filter")
    search_col1, search_col2 = st.columns(2)
    
    with search_col1:
        equipment_filter = st.selectbox("Filter by Equipment Type:", ["All"] + sorted(list(df_motors["equipment"].dropna().unique())))
    with search_col2:
        search_query = st.text_input("🔍 Quick Search (Drive, Frame, Matcode):", "").lower()
        
    filtered_df = df_motors.copy()
    if equipment_filter != "All":
        filtered_df = filtered_df[filtered_df["equipment"] == equipment_filter]
    if search_query:
        filtered_df = filtered_df[
            filtered_df["drive"].str.lower().str.contains(search_query, na=False) |
            filtered_df["frame"].str.lower().str.contains(search_query, na=False) |
            filtered_df["matcode"].str.lower().str.contains(search_query, na=False)
        ]
        
    st.markdown(f"**Showing {len(filtered_df)} Matching Motors**")
    
    def highlight_status(row):
        if row['status'] == 'Breakdown': return ['background-color: #ffcccc'] * len(row)
        elif row['status'] == 'Under Maintenance': return ['background-color: #fff2cc'] * len(row)
        return [''] * len(row)
        
    if not filtered_df.empty:
        st.dataframe(filtered_df.style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)
    else:
        st.info("No records match your active search terms.")

# ==================== TAB 2: FIELD STATUS UPDATE ====================
with tab_update:
    st.subheader("Append / Edit Status & Remarks")
    if df_motors.empty:
        st.warning("Please populate the Master Data Registry first via Tab 3.")
    else:
        df_motors["selector_label"] = "ID " + df_motors["id"].astype(str) + " | " + df_motors["equipment"].astype(str) + " (" + df_motors["drive"].astype(str) + ")"
        selected_motor_label = st.selectbox("Select Target Motor to Modify:", df_motors["selector_label"].tolist())
        
        selected_row = df_motors[df_motors["selector_label"] == selected_motor_label].iloc[0]
        m_id = int(selected_row["id"])
        
        st.info(f"📍 Modifying: {selected_row['equipment']} - {selected_row['drive']}")
        
        with st.form("status_update_form"):
            up_col1, up_col2 = st.columns(2)
            with up_col1:
                current_status = selected_row["status"] if pd.notna(selected_row["status"]) else "Healthy"
                status_options = ["Healthy", "Under Observation", "Under Maintenance", "Breakdown", "Spare/Scrapped"]
                status_idx = status_options.index(current_status) if current_status in status_options else 0
                new_status = st.selectbox("Operational Status:", status_options, index=status_idx)
                
            with up_col2:
                current_remarks = selected_row["remarks"] if pd.notna(selected_row["remarks"]) else ""
                new_remarks = st.text_area("Field Remarks / Update Log:", value=current_remarks)
                
            if st.form_submit_button("Submit Operational Status Change"):
                update_motor_status(m_id, "status", new_status)
                update_motor_status(m_id, "remarks", new_remarks)
                st.success("Database status appended and successfully committed!")
                st.rerun()

# ==================== TAB 3: MASTER DATA ENTRY ====================
with tab_master:
    st.subheader("Add New Motor Asset to Master Database")
    with st.form("master_entry_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            eq = st.text_input("Equipment (e.g., Air Compressor, Oil Pump)")
            drv = st.text_input("Drive Name (e.g., Compressor motor west)")
            mat = st.text_input("Matcode")
            qty = st.number_input("Quantity", min_value=1, value=1, step=1)
        with c2:
            kw = st.number_input("Power Rating (kw/hp)", min_value=0.0, step=0.1, format="%.2f")
            rpm = st.number_input("RPM", min_value=0, value=1440, step=10)
            frm = st.text_input("Frame Dimension Size (e.g., 160M, 225M)")
            mnt = st.selectbox("Mount Configuration Type", ["foot", "flange", "foot/flange"])
        with c3:
            curr = st.number_input("Full Load Current (Amps)", min_value=0.0, step=0.1, format="%.2f")
            nl_curr = st.number_input("No Load Current (Amps)", min_value=0.0, step=0.1, format="%.2f")
            cpl = st.text_input("Coupling Details (e.g., pin bush, chain, bibby)")
            rem = st.text_input("Initial Master Database Remarks")
            
        if st.form_submit_button("Commit Motor to Registry"):
            if not eq or not drv:
                st.error("Validation Error: 'Equipment' and 'Drive Name' are required fields.")
            else:
                insert_motor((eq, drv, mat, qty, kw, rpm, frm, mnt, curr, nl_curr, cpl, "Healthy", rem))
                st.success(f"Successfully integrated '{drv}' into the system!")
                st.rerun()

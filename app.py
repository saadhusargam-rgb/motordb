import streamlit as st
import pandas as pd
import sqlite3
import io

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
            matcode TEXT,
            qty TEXT,
            kw_hp TEXT,
            rpm TEXT,
            frame TEXT,
            mount TEXT,
            current TEXT,
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

    search_col1, search_col2, search_col3 = st.columns(3)
    with search_col1:
        area_filter = st.selectbox("Filter by Area / Zone:", ["All"] + sorted(list(df_motors["area"].dropna().unique())) if not df_motors.empty else ["All"])
    with search_col2:
        equipment_filter = st.selectbox("Filter by Equipment Type:", ["All"] + sorted(list(df_motors["equipment"].dropna().unique())) if not df_motors.empty else ["All"])
    with search_col3:
        search_query = st.text_input("🔍 Keyword Search (Drive, Frame, Matcode):", "").lower()
        
    filtered_df = df_motors.copy()
    if not filtered_df.empty:
        if area_filter != "All":
            filtered_df = filtered_df[filtered_df["area"] == area_filter]
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
        display_cols = ["id", "area", "equipment", "drive", "matcode", "qty", "kw_hp", "rpm", "frame", "mount", "current", "no_load_current", "coupling", "status", "remarks"]
        st.dataframe(filtered_df[display_cols].style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)
    else:
        st.info("No records found in database registry. Please add entries in the Master Data Entry tab.")

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
            # Safe extraction using .iloc to fix the KeyError/TypeError
            selected_row = matched_rows.iloc[0]
            m_id = int(selected_row["id"])
            m_area = str(selected_row["area"])
            m_eq = str(selected_row["equipment"])
            m_drv = str(selected_row["drive"])
            m_status = str(selected_row["status"])
            m_remarks = str(selected_row["remarks"])
            
            st.info(f"📍 Modifying: Area {m_area} -> {m_eq} ({m_drv})")
            
            with st.form("status_update_form"):
                up_col1, up_col2 = st.columns(2)
                with up_col1:
                    current_status = m_status if m_status and m_status != "None" and m_status != "" else "Healthy"
                    status_options = ["Healthy", "Under Observation", "Under Maintenance", "Breakdown", "Spare/Scrapped"]
                    status_idx = status_options.index(current_status) if current_status in status_options else 0
                    new_status = st.selectbox("Operational Status:", status_options, index=status_idx)
                    
                with up_col2:
                    current_remarks = m_remarks if m_remarks and m_remarks != "None" else ""
                    new_remarks = st.text_area("Field Remarks / Update Log:", value=current_remarks)
                    
                if st.form_submit_button("Submit Operational Status Change"):
                    update_motor_status(m_id, "status", new_status)
                    update_motor_status(m_id, "remarks", new_remarks)
                    st.success("Database status appended and successfully committed!")
                    st.rerun()

# ==================== TAB 3: MASTER DATA ENTRY ====================
with tab_master:
    st.subheader("Bulk Import via Excel Spreadsheet (.xlsx)")
    st.markdown("Ensure your Excel columns match these names: **Area, Equipment, Drive, Matcode, Qty, kw/hp, rpm, frame, mount, current, coupling, remarks**")
    
    uploaded_excel = st.file_uploader("Upload Motor List Spreadsheet File", type=["xlsx"])
    
    if uploaded_excel is not None:
        excel_df = pd.read_excel(uploaded_excel, engine="openpyxl")
        
        for col in excel_df.columns:
            excel_df[col] = excel_df[col].astype(str).replace(['nan', 'NaN', 'None', '<NA>'], '')
        
        st.write("📊 Previewing Raw Uploaded Excel Sheet Data Structure:")
        st.dataframe(excel_df, use_container_width=True)
        
        if st.button("Confirm Bulk Import into SQLite Engine"):
            import_counter = 0
            skipped_counter = 0
            
            for index, row in excel_df.iterrows():
                area_val = str(row.get("Area", row.get("area", ""))).strip()
                eq_val = str(row.get("Equipment", row.get("equipment", ""))).strip()
                drv_val = str(row.get("Drive", row.get("drive", ""))).strip()
                mat_val = str(row.get("Matcode", row.get("matcode", ""))).strip()
                qty_val = str(row.get("Qty", row.get("qty", ""))).strip()
                kw_val = str(row.get("kw/hp", row.get("kw_hp", ""))).strip()
                rpm_val = str(row.get("rpm", row.get("RPM", ""))).strip()
                frame_val = str(row.get("frame", row.get("Frame", ""))).strip()
                mount_val = str(row.get("mount", row.get("Mount", ""))).strip()
                curr_val = str(row.get("current", row.get("Current", ""))).strip()
                nl_curr_val = str(row.get("no_load_current", "")).strip()
                cpl_val = str(row.get("coupling", row.get("Coupling", ""))).strip()
                rem_val = str(row.get("remarks", row.get("Remarks", ""))).strip()
                
                # Dynamic Check: Only skip rows that are completely missing BOTH Area and Equipment
                if not area_val or not eq_val:
                    skipped_counter += 1
                    continue
                
                insert_motor((area_val, eq_val, drv_val, mat_val, qty_val, kw_val, rpm_val, frame_val, mount_val, curr_val, nl_curr_val, cpl_val, "Healthy", rem_val))
                import_counter += 1
                
            st.success(f"🚀 Import process executed! Successfully processed {import_counter} database rows.")

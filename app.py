import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re

# --- APP LAYOUT CONFIGURATION ---
st.set_page_config(page_title="Motor Cloud Sync Manager", layout="wide")

st.title("⚡ Industrial Motor Tracker (Google Drive Live Sync)")
st.markdown("All updates made here or directly on the Google Sheet sync both ways instantly.")

# --- INITIALIZE LIVE GOOGLE SHEETS CONNECTION ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Read the data sheet natively
    df_motors = conn.read(ttl=2)
except Exception as e:
    st.error(f"Failed to connect to Google Drive Sheet. Verify your connection link tokens in Secrets. Error: {e}")
    st.stop()

# Auto-detect column naming structures and map lowercase versions for layout safety
if not df_motors.empty:
    df_motors.columns = [str(c).lower().strip() for c in df_motors.columns]
    
    # Fill missing value empty spaces with clear blank elements
    for col in df_motors.columns:
        df_motors[col] = df_motors[col].fillna("").astype(str).str.strip()
    
    if "status" not in df_motors.columns:
        df_motors["status"] = "Healthy"
    df_motors["status"] = df_motors["status"].replace("", "Healthy")
else:
    st.warning("⚠️ **Data Structural Error:** Connected successfully, but your worksheet table contains zero data rows or headers.")
    st.stop()

# --- UTILITIES ---
def sanitize_digits(val, max_digits):
    if pd.isna(val) or val is None or str(val).strip().lower() in ['nan', 'none', '']:
        return ""
    cleaned = re.sub(r'[^0-9.]', '', str(val).strip())
    if "." in cleaned:
        parts = cleaned.split('.')
        integer_part = parts[0][:max_digits]
        decimal_part = "".join(parts[1:])[:2]
        return f"{integer_part}.{decimal_part}".strip('.')
    return cleaned[:max_digits]

def safe_decimal_formatter(val):
    if pd.isna(val) or val is None or str(val).strip().lower() in ['nan', 'none', '']:
        return ""
    try:
        numeric_value = float(val)
        return f"{numeric_value:.2f}"
    except (ValueError, TypeError):
        return str(val)

tab_view, tab_update, tab_master = st.tabs(["🔍 Search & View Live Fleet", "⚙️ Field Status Update", "🏗️ Add Single Motor Asset"])

# ==================== TAB 1: LIVE SEARCH & VIEW ====================
with tab_view:
    st.subheader("Quick Search Filter")
    
    search_col1, search_col2, search_col3, search_col4 = st.columns(4)
    with search_col1:
        area_filter = st.selectbox("Filter by Area / Zone:", ["All"] + sorted(list(df_motors["area"].unique())))
    with search_col2:
        equipment_filter = st.selectbox("Filter by Equipment Type:", ["All"] + sorted(list(df_motors["equipment"].unique())))
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
                filtered_df["matcode"].str.lower().str.contains(search_query, na=False)
            ]
        
    st.markdown(f"**Showing {len(filtered_df)} Matching Motors from Google Drive**")
    
    def highlight_status_column(series):
        if series.name == 'status':
            styles = []
            for val in series:
                status = str(val).strip()
                if status == 'Healthy': styles.append('background-color: #d4edda; color: #155724;')
                elif status == 'Under Observation': styles.append('background-color: #d1ecf1; color: #0c5460;')
                elif status == 'Under Maintenance': styles.append('background-color: #fff3cd; color: #856404;')
                elif status == 'Breakdown': styles.append('background-color: #f8d7da; color: #721c24; font-weight: bold;')
                elif status == 'Spare/Scrapped': styles.append('background-color: #e2e3e5; color: #383d41;')
                else: styles.append('')
            return styles
        return [''] * len(series)
        
    if not filtered_df.empty:
        display_cols = [c for col in ["area", "equipment", "drive", "matcode", "qty", "kw_hp", "rpm", "frame", "mount", "current", "no_load_current", "coupling", "status", "remarks"] if (c:=col) in filtered_df.columns]
        
        formatted_styled_df = (
            filtered_df[display_cols]
            .style.apply(highlight_status_column, axis=0)
            .format({
                "matcode": safe_decimal_formatter,
                "kw/hp": safe_decimal_formatter,
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
        st.warning("Please populate your Google Sheet rows first.")
    else:
        df_motors["selector_label"] = "Loc: " + df_motors["area"] + " | Eq: " + df_motors["equipment"] + " (" + df_motors["drive"] + ")"
        selected_motor_label = st.selectbox("Select Target Motor to Modify:", df_motors["selector_label"].tolist())
        
        matched_indices = df_motors[df_motors["selector_label"] == selected_motor_label].index
        if len(matched_indices) > 0:
            target_idx = matched_indices[0]
            selected_row = df_motors.loc[target_idx]
            
            st.info(f"📍 Modifying: Area {selected_row['area']} -> {selected_row['equipment']} ({selected_row['drive']})")
            
            with st.form("status_update_form"):
                current_status = selected_row["status"]
                status_options_edit = ["Healthy", "Under Observation", "Under Maintenance", "Breakdown", "Spare/Scrapped"]
                status_idx = status_options_edit.index(current_status) if current_status in status_options_edit else 0
                
                new_status = st.selectbox("Operational Status:", status_options_edit, index=status_idx)
                new_remarks = st.text_area("Field Remarks / Update Log:", value=selected_row["remarks"])
                
                submit_status = st.form_submit_button("Submit & Write-Back to Google Drive")
                
            if submit_status:
                df_motors.loc[target_idx, "status"] = new_status
                df_motors.loc[target_idx, "remarks"] = new_remarks
                
                if "selector_label" in df_motors.columns:
                    df_motors = df_motors.drop(columns=["selector_label"])
                
                # Write back targeting active worksheet natively
                conn.update(data=df_motors)
                st.success("✅ Change committed! Google Sheet updated in real time.")
                st.rerun()

# ==================== TAB 3: MASTER DATA ENTRY ====================
with tab_master:
    st.subheader("Add Single Motor Asset Manually to Cloud Registry")
    
    with st.form("manual_entry_form"):
        st.markdown("##### 📌 Location & Identification")
        area_input = st.text_input("Area / Shop / Zone Location*")
        eq = st.text_input("Equipment Name*")
        drv = st.text_input("Drive Name")
        mat_in = st.text_input("Matcode (Max 12 digits)")
        
        st.markdown("##### ⚙️ Technical Design Parameters")
        qty = st.text_input("Quantity", value="1")
        kw_in = st.text_input("Power Rating kw/hp (Max 6 digits)")
        rpm_in = st.text_input("RPM Speed (Max 5 digits)")
        frm = st.text_input("Frame Dimension Size")
        mnt = st.text_input("Mount Configuration Type")
        
        st.markdown("##### ⚡ Electrical Ratings & Coupling")
        curr_in = st.text_input("Full Load Current Amps (Max 6 digits)")
        nl_curr = st.text_input("No Load Current Amps")
        cpl = st.text_input("Coupling Details")
        
        st.markdown("##### 📈 Operational Status & Log")
        init_status = st.selectbox("Initial Operational Status:", ["Healthy", "Under Observation", "Under Maintenance", "Breakdown", "Spare/Scrapped"])
        rem = st.text_area("Initial Master Database Remarks", value="Manually entered asset record.")
        
        submit_btn = st.form_submit_button("💾 Append to Google Sheet")
        if submit_btn:
            if not area_input or not eq:
                st.error("Validation Error: 'Area' and 'Equipment Name' are required fields.")
            else:
                matcode_val = sanitize_digits(mat_in, max_digits=12)
                current_val = sanitize_digits(curr_in, max_digits=6)
                kw_val = sanitize_digits(kw_in, max_digits=6)
                rpm_val = sanitize_digits(rpm_in, max_digits=5)
                
                row_data = {
                    "area": area_input,
                    "equipment": eq,
                    "drive": drv,
                    "matcode": matcode_val,
                    "qty": qty,
                    "kw/hp": kw_val,
                    "rpm": rpm_val,
                    "frame": frm,
                    "mount": mnt,

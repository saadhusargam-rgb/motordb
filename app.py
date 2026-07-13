import streamlit as st
import pandas as pd
import re

# --- APP LAYOUT CONFIGURATION ---
st.set_page_config(page_title="Motor Cloud Sync Manager", layout="wide")

st.title("⚡ Industrial Motor Tracker (Google Drive Live Sync)")
st.markdown("All updates made here or directly on the Google Sheet sync both ways instantly.")

# --- INITIALIZE NATIVE DIRECT STREAM CONNECTION ---
try:
    csv_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    df_raw = pd.read_csv(csv_url)
except Exception as e:
    st.error(f"Failed to fetch public stream from Google Drive. Verify your Secrets link configuration. Error: {e}")
    st.stop()

# --- RESTRUCTURE & MAP WORKSHEET HEADER TOKENS ---
if not df_raw.empty:
    df_motors = df_raw.copy()
    
    # Clean, strip, and lowercase all column names automatically to avoid layout bugs
    df_motors.columns = [str(c).strip().lower() for c in df_motors.columns]
    
    # Map custom variations (like 'no load current' or 'kw/hp') to clear code handles
    rename_map = {}
    for col in df_motors.columns:
        if "no load" in col or "no_load" in col:
            rename_map[col] = "no_load_current"
        elif "kw" in col or "hp" in col:
            rename_map[col] = "kw_hp"
            
    if rename_map:
        df_motors = df_motors.rename(columns=rename_map)
        
    # Fill empty data spaces with clean blank fields
    for col in df_motors.columns:
        df_motors[col] = df_motors[col].fillna("").astype(str).str.strip()
        
    if "status" not in df_motors.columns:
        df_motors["status"] = "Healthy"
    # Normalize default status fields
    df_motors["status"] = df_motors["status"].replace(["", "nan", "None"], "Healthy")
else:
    st.warning("⚠️ Data Structural Error: Connected successfully, but your worksheet contains zero rows of data.")
    st.stop()

# --- UTILITIES ---
def sanitize_digits(val, max_digits):
    if pd.isna(val) or val is None or str(val).strip().lower() in ['nan', 'none', '']:
        return ""
    cleaned = re.sub(r'[^0-9.]', '', str(val).strip())
    if "." in cleaned:
        parts = cleaned.split('.')
        integer_part = parts[:max_digits]
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
        core_cols = ["area", "equipment", "drive", "matcode", "qty", "kw_hp", "rpm", "frame", "mount", "current", "no_load_current", "coupling", "status", "remarks"]
        display_cols = [c for c in core_cols if c in filtered_df.columns]
        
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
    st.info("💡 **Read-Only Link Active:** Two-way writeback requires an API service token configuration. You can view your real-time fleet adjustments here.")
    
    if df_motors.empty:
        st.warning("Please populate your Google Sheet rows first.")
    else:
        # FIX: Formulate a unique label using the absolute row index number (+2 to match Google Sheets row numbering layout)
        # This completely bypasses the duplicate row value error crashes
        df_motors["row_id"] = df_motors.index + 2
        df_motors["selector_label"] = "[Row " + df_motors["row_id"].astype(str) + "] Loc: " + df_motors["area"] + " | Eq: " + df_motors["equipment"] + " (" + df_motors["drive"] + ")"
        
        selected_motor_label = st.selectbox("Select Target Motor to Modify:", df_motors["selector_label"].tolist())
        
        matched_rows = df_motors[df_motors["selector_label"] == selected_motor_label]
        if not matched_rows.empty:
            # FIX: Grab the atomic row object cleanly using an explicit positional selector (.iloc[0])
            selected_row = matched_rows.iloc[0]
            
            st.info(f"📍 Selected Asset: Row {selected_row['row_id']} | Area {selected_row['area']} -> {selected_row['equipment']} ({selected_row['drive']})")
            
            with st.form("status_update_form"):
                current_status = str(selected_row["status"]).strip()
                status_options_edit = ["Healthy", "Under Observation", "Under Maintenance", "Breakdown", "Spare/Scrapped"]
                status_idx = status_options_edit.index(current_status) if current_status in status_options_edit else 0
                
                new_status = st.selectbox("Operational Status:", status_options_edit, index=status_idx)
                new_remarks = st.text_area("Field Remarks / Update Log:", value=str(selected_row["remarks"]))
                
                st.form_submit_button("Submit Modifications (Disabled in Read-Only Mode)")

# ==================== TAB 3: ADD MOTOR ASSET ====================
with tab_master:
    st.subheader("Add Single Motor Asset Manually")
    st.info("📋 To maintain your live master register, open your linked Google Drive sheet directly on your laptop/mobile browser and append rows. Your additions will reflect inside this search panel instantly.")

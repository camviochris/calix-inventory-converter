import streamlit as st
import pandas as pd
import datetime
import io
import re
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config(page_title="Calix Inventory Import Tool", layout="wide")
st.title("📥 Calix Inventory Import Tool")
st.markdown("🔒 **All data is processed in-memory. No files or customer data are stored.**")

# --- Session State Initialization ---
if "devices" not in st.session_state:
    st.session_state.devices = []
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "df" not in st.session_state:
    st.session_state.df = None
if "company_name" not in st.session_state:
    st.session_state.company_name = ""
if "custom_location" not in st.session_state:
    st.session_state.custom_location = ""

# --- Clear Session State ---
def clear_session():
    keys_to_clear = list(st.session_state.keys())
    for key in keys_to_clear:
        del st.session_state[key]

st.sidebar.button("🔄 Start Over", on_click=clear_session)

# --- Step 1: File Upload ---
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    file = st.file_uploader("Upload your .csv or .xlsx file", type=["csv", "xlsx"])
    if file:
        try:
            df_preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
            st.write("### Preview First 5 Rows:")
            st.dataframe(df_preview.head())
            header_row = st.radio("Select the row that contains column headers", df_preview.index[:5])
            if st.button("✅ Set Header Row"):
                df = pd.read_csv(file, skiprows=header_row) if file.name.endswith(".csv") else pd.read_excel(file, skiprows=header_row)
                df.columns = df.columns.str.strip()
                st.session_state.df = df
                st.session_state.header_confirmed = True
                st.rerun()
        except Exception as e:
            st.error(f"Error reading file: {e}")

# --- Step 2: Add Devices ---
if st.session_state.header_confirmed:
    with st.expander("🛠️ Step 2: Add Devices to Convert", expanded=True):
        with st.form("device_form"):
            device_name = st.text_input("Enter device model name ℹ️", help="Match the format used in the Description column.")
            device_types = ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"]
            selected_type = st.selectbox("What type of device is this?", device_types)
            location = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom"])
            if location == "Custom":
                custom_location = st.text_input("Enter custom location (match Camvio exactly)")
                st.warning("⚠️ This must match Camvio Web **exactly** or it will fail.")
            else:
                custom_location = location

            lookup_clicked = st.form_submit_button("🔍 Look Up Device")

            default_port = ""
            default_profile = device_name.upper()
            warning = ""

            if lookup_clicked and device_name:
                mapped_type = device_profile_name_map.get(device_name.upper())
                template = device_numbers_template_map.get(device_name.upper())
                if template:
                    port_match = re.search(r"ONT_PORT=([^|]*)", template)
                    profile_match = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                    default_port = port_match.group(1) if port_match else ""
                    default_profile = profile_match.group(1).upper() if profile_match else default_profile

                # Normalize device types for comparison
                normalize_map = {
                    "CX_ROUTER": "ROUTER",
                    "CX_MESH": "MESH",
                    "CX_SFP": "SFP",
                    "GAM_COAX_ENDPOINT": "ENDPOINT",
                    "ONT": "ONT"
                }
                mapped_type_normalized = normalize_map.get(mapped_type, mapped_type)
                selected_type_normalized = selected_type

                if mapped_type and mapped_type_normalized != selected_type_normalized:
                    if selected_type == "ONT":
                        st.warning(f"⚠️ This device is typically mapped as **{mapped_type_normalized}**. "
                                   f"You selected **ONT**, which could affect provisioning. "
                                   f"Please verify your setup supports this device as an ONT.")
                    else:
                        st.info(f"ℹ️ Note: This device is usually mapped as **{mapped_type_normalized}**, "
                                f"but you've selected **{selected_type_normalized}**. Make sure your system is set up for this.")

            if selected_type == "ONT":
                ont_port = st.text_input("ONT_PORT", value=default_port)
                ont_profile = st.text_input("ONT_PROFILE_ID", value=default_profile)
            else:
                ont_port = ""
                ont_profile = ""

            if st.form_submit_button("➕ Add Device"):
                st.session_state.devices.append({
                    "device_name": device_name,
                    "device_type": selected_type,
                    "location": custom_location,
                    "ONT_PORT": ont_port,
                    "ONT_PROFILE_ID": ont_profile,
                    "ONT_MOMENTUM_PASSWORD": "NO VALUE"
                })

        if st.session_state.devices:
            st.subheader("Devices Selected:")
            for idx, d in enumerate(st.session_state.devices):
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.markdown(f"**🔹 {d['device_name']} → {d['device_type']} @ {d['location']}**")
                    if d["device_type"] == "ONT":
                        st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE")
                with col2:
                    if st.button("🗑️ Remove", key=f"remove_{idx}"):
                        st.session_state.devices.pop(idx)
                        st.rerun()

# Step 3 is unchanged — only Step 2 logic was touched.

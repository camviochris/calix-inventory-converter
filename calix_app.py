# ==============================================
# GitHub Commit Template
# ----------------------------------------------
# Commit Summary:
# Add inline ℹ️ tooltips for user guidance
#
# Commit Description:
# - Adds small explanatory tooltips next to key fields using ℹ️ icon
# - Covers header row, device name, device type, location, ONT settings
# - Footer updated to v2.22
# ==============================================

import streamlit as st
import pandas as pd
import re
import io
import datetime
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config(page_title="Calix Inventory Import", layout="centered")
st.title("📥 Calix Inventory Import Tool")

# Session state
if "devices" not in st.session_state:
    st.session_state.devices = []
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "device_lookup" not in st.session_state:
    st.session_state.device_lookup = {}

# Step 1: Upload file and confirm header
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    file = st.file_uploader("Upload your .csv or .xlsx file", type=["csv", "xlsx"])
    df = None

    if file:
        try:
            df_preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
            st.write("### Preview First 5 Rows:")
            st.dataframe(df_preview.head())

            header_row = st.radio("Which row contains the column headers? ℹ️", df_preview.index[:5], help="Choose the row that contains actual field names like Serial Number, MAC, etc.")
            if st.button("✅ Set Header Row"):
                df = pd.read_csv(file, skiprows=header_row) if file.name.endswith(".csv") else pd.read_excel(file, skiprows=header_row)
                df.columns = df.columns.str.strip()
                st.session_state.df = df
                st.session_state.header_confirmed = True
                st.rerun()
        except Exception as e:
            st.error(f"Error reading file: {e}")

# Step 2: Collect device info
if "df" in st.session_state:
    st.markdown("---")
    st.header("🔧 Step 2: Add Devices to Convert")
    with st.form("device_form"):
        device_name = st.text_input("Enter device model name ℹ️", help="Found in the Description column of your file")
        load_defaults = st.form_submit_button("🔍 Look Up Device")

        default_type = "ONT"
        default_port = ""
        default_profile_id = ""
        default_password = "no value"
        device_found = False

        if load_defaults:
            st.session_state.device_lookup = {"device_name": device_name, "warning_shown": False}
            if device_name in device_profile_name_map:
                device_found = True
                default_type = device_profile_name_map[device_name]
                template = device_numbers_template_map.get(device_name, "")
                match_port = re.search(r"ONT_PORT=([^|]*)", template)
                match_profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                default_port = match_port.group(1) if match_port else ""
                default_profile_id = match_profile.group(1) if match_profile else ""

        device_types = ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"]
        mapped_type = device_profile_name_map.get(device_name)
        default_index = device_types.index(mapped_type) if mapped_type in device_types else 0
        selected_index = st.selectbox("What type of device is this? ℹ️", device_types, index=default_index if load_defaults else 0, key="device_type_selector", help="Make sure this matches how your system provisions this device")
        device_type = selected_index if isinstance(selected_index, str) else device_types[default_index]

        # If device not found and selected as ONT
        if load_defaults and not device_found and device_type == "ONT":
            st.warning("🚧 This device model name was not found in memory. You can still proceed as ONT by providing required settings.\n\nPlease provide the `ONT_PORT` and `ONT_PROFILE_ID` based on how it's setup in your system.\nIf this device is not in your Camvio inventory, it may fail provisioning. Please contact Camvio Support to add it.")

        if load_defaults and device_name in device_profile_name_map and mapped_type != device_type:
            st.warning(f"⚠️ This device is typically identified as `{mapped_type}`. If you're using `{device_type}`, ensure your provisioning is setup and verified accordingly.")

        location = st.selectbox("Where should it be stored? ℹ️", ["WAREHOUSE", "Custom..."], help="Camvio must have this location EXACTLY as shown. Case and spelling matter.")
        if location == "Custom...":
            location = st.text_input("Enter custom location (must match Camvio EXACTLY)")
            st.warning("⚠️ This must exactly match the spelling/case in Camvio or it will fail.")

        custom_ont_port = ""
        custom_profile_id = ""
        if device_type == "ONT":
            st.markdown("#### Customize ONT Settings (required for custom devices)")
            custom_ont_port = st.text_input("ONT_PORT ℹ️", value=default_port, help="The interface this ONT uses to connect (e.g., G1 or x1)")
            custom_profile_id = st.text_input("ONT_PROFILE_ID ℹ️", value=default_profile_id or device_name, help="Provisioning profile used in your system")

        add_device = st.form_submit_button("➕ Add Device")

        if add_device and device_name:
            st.session_state.devices.append({
                "device_name": device_name.strip(),
                "device_type": device_type,
                "location": location.strip(),
                "ONT_PORT": custom_ont_port.strip(),
                "ONT_PROFILE_ID": custom_profile_id.strip(),
                "ONT_MOMENTUM_PASSWORD": "no value"
            })

    if st.session_state.devices:
        st.write("### Devices Selected:")
        for i, d in enumerate(st.session_state.devices):
            cols = st.columns([5, 1])
            with cols[0]:
                st.write(f"🔹 {d['device_name']} → {d['device_type']} @ {d['location']}")
                if d["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: no value", language="text")
            with cols[1]:
                if st.button("🗑️ Remove", key=f"remove_{i}"):
                    st.session_state.devices.pop(i)
                    st.rerun()

# Footer
st.markdown("---")
st.markdown("<div style='text-align: right; font-size: 0.75em; color: gray;'>Last updated: 2025-04-03 • Rev: v2.22</div>", unsafe_allow_html=True)

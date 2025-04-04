# ==============================================
# GitHub Commit Template
# ----------------------------------------------
# Commit Summary:
# Fix warning reset after device type change
#
# Commit Description:
# - Ensures that warning message resets when the user changes the device type after lookup
# - Maintains device model validation with fallback for unmatched profiles
# - Keeps Step 1 auto-collapse behavior
# - Updated footer version to v2.19
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

            header_row = st.radio("Which row contains the column headers?", df_preview.index[:5])
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
        device_name = st.text_input("Enter device model name (as found in Description column)")
        load_defaults = st.form_submit_button("🔍 Look Up Device")

        default_type = "ONT"
        default_port = ""
        default_profile_id = ""
        default_password = "no value"

        if load_defaults:
            st.session_state.device_lookup = {"device_name": device_name, "warning_shown": False}
            if device_name in device_profile_name_map:
                default_type = device_profile_name_map[device_name]
                template = device_numbers_template_map.get(device_name, "")
                match_port = re.search(r"ONT_PORT=([^|]*)", template)
                match_profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                match_pass = re.search(r"ONT_MOMENTUM_PASSWORD=([^|]*)", template)
                default_port = match_port.group(1) if match_port else ""
                default_profile_id = match_profile.group(1) if match_profile else ""
                default_password = match_pass.group(1) if match_pass else "no value"

        device_types = ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"]
        mapped_type = device_profile_name_map.get(device_name)
        default_index = device_types.index(mapped_type) if mapped_type in device_types else 0
        selected_index = st.selectbox("What type of device is this?", device_types, index=default_index if load_defaults else 0, key="device_type_selector")
        device_type = selected_index if isinstance(selected_index, str) else device_types[default_index]

        # Only show warning if type differs AND the lookup just happened
        if load_defaults and device_name in device_profile_name_map and mapped_type != device_type:
            st.warning(f"⚠️ This device is typically identified as `{mapped_type}`. If you're using `{device_type}`, ensure your provisioning is setup and verified accordingly.")

        location = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom..."])
        if location == "Custom...":
            location = st.text_input("Enter custom location (must match Camvio EXACTLY)")
            st.warning("⚠️ This must exactly match the spelling/case in Camvio or it will fail.")

        custom_ont_port = ""
        custom_profile_id = ""
        custom_password = ""
        if device_type == "ONT":
            st.markdown("#### Customize ONT Settings (optional)")
            custom_ont_port = st.text_input("ONT_PORT", value=default_port)
            custom_profile_id = st.text_input("ONT_PROFILE_ID", value=default_profile_id or device_name)
            custom_password = st.text_input("ONT_MOMENTUM_PASSWORD", value=default_password)

        add_device = st.form_submit_button("➕ Add Device")

        if add_device and device_name:
            st.session_state.devices.append({
                "device_name": device_name.strip(),
                "device_type": device_type,
                "location": location.strip(),
                "ONT_PORT": custom_ont_port.strip(),
                "ONT_PROFILE_ID": custom_profile_id.strip(),
                "ONT_MOMENTUM_PASSWORD": custom_password.strip()
            })

    if st.session_state.devices:
        st.write("### Devices Selected:")
        for i, d in enumerate(st.session_state.devices):
            cols = st.columns([5, 1])
            with cols[0]:
                st.write(f"🔹 {d['device_name']} → {d['device_type']} @ {d['location']}")
                if d["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: {d['ONT_MOMENTUM_PASSWORD']}", language="text")
            with cols[1]:
                if st.button("🗑️ Remove", key=f"remove_{i}"):
                    st.session_state.devices.pop(i)
                    st.rerun()

# Footer
st.markdown("---")
st.markdown("<div style='text-align: right; font-size: 0.75em; color: gray;'>Last updated: 2025-04-03 • Rev: v2.20</div>", unsafe_allow_html=True)

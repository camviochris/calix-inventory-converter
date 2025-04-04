import streamlit as st
import pandas as pd
import re
import io
import datetime
from collections import Counter
from mappings import device_profile_name_map, device_numbers_template_map

# Session state management for header confirmation
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "df" not in st.session_state:
    st.session_state.df = None

# Step 1: Upload file and confirm header
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    if st.session_state.header_confirmed:
        st.success("✅ Step 1 completed")
    file = st.file_uploader("Upload your .csv or .xlsx file", type=["csv", "xlsx"])
    df = None

    if file:
        try:
            # Read the file and show preview
            df_preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
            st.write("### Preview First 5 Rows:")
            st.dataframe(df_preview.head())

            # Choose header row
            header_row = st.radio("Which row contains the column headers? ℹ️", df_preview.index[:5], help="Choose the row that contains actual field names like Serial Number, MAC, etc.")
            if st.button("✅ Set Header Row"):
                df = pd.read_csv(file, skiprows=header_row) if file.name.endswith(".csv") else pd.read_excel(file, skiprows=header_row)
                df.columns = df.columns.str.strip()
                st.session_state.df = df
                st.session_state.header_confirmed = True
                st.rerun()  # Re-run the app to proceed to Step 2

        except Exception as e:
            st.error(f"Error reading file: {e}")
        
# Continue with Step 2 and Step 3 after this part

# STEP 2: Add Devices to Convert
with st.expander("🔧 Step 2: Add Devices to Convert", expanded=True):
    st.markdown("### Add Devices to Convert")

    if "devices" not in st.session_state:
        st.session_state.devices = []

    if "device_lookup_data" not in st.session_state:
        st.session_state.device_lookup_data = {}

    with st.form("device_lookup_form", clear_on_submit=False):
        device_name_input = st.text_input("Enter device model name ℹ️", help="Found in the Description column of your file")
        lookup_clicked = st.form_submit_button("🔍 Look Up Device")

        if lookup_clicked:
            device_key = device_name_input.strip().upper()
            st.session_state.device_lookup_data = {
                "device_name": device_name_input.strip(),
                "device_key": device_key,
                "type": device_profile_name_map.get(device_key, "ONT"),
                "ONT_PORT": "",
                "ONT_PROFILE_ID": device_key,
            }

            template = device_numbers_template_map.get(device_key, "")
            port_match = re.search(r"ONT_PORT=([^|]*)", template)
            profile_match = re.search(r"ONT_PROFILE_ID=([^|]*)", template)

            if port_match:
                st.session_state.device_lookup_data["ONT_PORT"] = port_match.group(1)
            if profile_match:
                st.session_state.device_lookup_data["ONT_PROFILE_ID"] = profile_match.group(1).upper()

        # Default values if lookup was successful or not
        device_types = ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"]
        mapped_type = data.get("type", "ONT")

        # Safely map values like CX_ROUTER → ROUTER
        mapped_friendly_type = (
            "ROUTER" if "ROUTER" in mapped_type else
            "MESH" if "MESH" in mapped_type else
            "SFP" if "SFP" in mapped_type else
            "ENDPOINT" if "ENDPOINT" in mapped_type else
            "ONT"
        )

        device_type = st.selectbox(
            "What type of device is this?",
            device_types,
            index=device_types.index(mapped_friendly_type),
            help="Make sure this matches how your system provisions this device"
        )

        # Only show ONT fields if ONT
        ont_port = ""
        ont_profile_id = ""
        if device_type == "ONT":
            ont_port = st.text_input("ONT_PORT", value=data.get("ONT_PORT", ""), key="ont_port_input")
            ont_profile_id = st.text_input("ONT_PROFILE_ID", value=data.get("ONT_PROFILE_ID", "").upper(), key="ont_profile_input")

        add_device = st.form_submit_button("➕ Add Device")

        if add_device:
            # Add whatever values are present in those fields
            st.session_state.devices.append({
                "device_name": data.get("device_name", device_name_input.strip()),
                "device_type": device_type,
                "location": location,
                "ONT_PORT": ont_port.strip() if device_type == "ONT" else "",
                "ONT_PROFILE_ID": ont_profile_id.strip().upper() if device_type == "ONT" else "",
                "ONT_MOMENTUM_PASSWORD": "NO VALUE"
            })

    if st.session_state.devices:
        st.markdown("### Devices Selected:")
        for i, d in enumerate(st.session_state.devices):
            cols = st.columns([6, 1])
            with cols[0]:
                st.write(f"🔹 {d['device_name']} → {d['device_type']} @ {d['location']}")
                if d["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE")
            with cols[1]:
                if st.button("🗑️ Remove", key=f"remove_{i}"):
                    st.session_state.devices.pop(i)
                    st.rerun()


import streamlit as st
import pandas as pd
import re
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config("Calix Inventory Import Tool", layout="wide")
st.title("📥 Calix Inventory Import Tool")
st.info("🔒 This tool processes everything in-memory and does **not** store any files or customer data.", icon="🔐")

# ---------- SESSION STATE ----------
if "devices" not in st.session_state:
    st.session_state.devices = []
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "df" not in st.session_state:
    st.session_state.df = None

# ---------- STEP 1 ----------
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    file = st.file_uploader("Upload your .csv or .xlsx file", type=["csv", "xlsx"])
    if file:
        try:
            df_preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
            st.subheader("Preview First 5 Rows:")
            st.dataframe(df_preview.head())

            header_row = st.radio(
                "Which row contains the column headers?",
                options=df_preview.index[:5],
                help="Choose the row with fields like Serial Number, MAC, etc."
            )

            if st.button("✅ Set Header Row"):
                df = pd.read_csv(file, skiprows=header_row) if file.name.endswith(".csv") else pd.read_excel(file, skiprows=header_row)
                df.columns = df.columns.str.strip()
                st.session_state.df = df
                st.session_state.header_confirmed = True
                st.success("✅ Step 1 completed! You can now proceed to Step 2.")
        except Exception as e:
            st.error(f"Error reading file: {e}")

# ---------- STEP 2 ----------
if st.session_state.header_confirmed:
with st.expander("🔧 Step 2: Add Devices to Convert", expanded=True):
    with st.form("device_form"):
        # 1. Inputs
        device_name = st.text_input("Enter device model name ℹ️", help="Found in the Description column of your file")

        device_types = ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"]
        selected_type = st.selectbox("What type of device is this?", device_types)

        location = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom..."])
        if location == "Custom...":
            location = st.text_input("Enter custom location (must match Camvio EXACTLY)")
            st.warning("⚠️ This must exactly match the Camvio inventory location, including capitalization and spelling.")

        # 2. Look Up Device (non-destructive)
        ont_port = ""
        ont_profile_id = device_name.upper()
        show_warning = False

        lookup = st.form_submit_button("🔍 Look Up Device")
        if lookup:
            # Case-insensitive match
            matched_key = next((k for k in device_profile_name_map if k.lower() == device_name.lower()), None)

            if matched_key:
                mapped_type = device_profile_name_map[matched_key]

                # Warn if type selected doesn't match what we expect
                mapped_friendly = (
                    "ROUTER" if "ROUTER" in mapped_type else
                    "MESH" if "MESH" in mapped_type else
                    "SFP" if "SFP" in mapped_type else
                    "ENDPOINT" if "ENDPOINT" in mapped_type else
                    "ONT"
                )

                if mapped_friendly != selected_type:
                    st.warning(f"⚠️ This device is typically identified as `{mapped_friendly}`. You selected `{selected_type}`. If this is intentional, make sure your provisioning supports it.")

                # Pull ONT defaults if it's an ONT in mapping (we won't force it to show)
                template = device_numbers_template_map.get(matched_key, "")
                port_match = re.search(r"ONT_PORT=([^|]*)", template)
                profile_match = re.search(r"ONT_PROFILE_ID=([^|]*)", template)

                if port_match:
                    ont_port = port_match.group(1).strip()
                if profile_match:
                    ont_profile_id = profile_match.group(1).strip().upper()
            else:
                st.warning("🚧 This device model name was not found in memory. You can still proceed manually.")

        # 3. Only show ONT fields if they selected ONT
        if selected_type == "ONT":
            st.markdown("#### Customize ONT Settings")
            ont_port = st.text_input("ONT_PORT", value=ont_port)
            ont_profile_id = st.text_input("ONT_PROFILE_ID", value=ont_profile_id)

        # 4. Add Device
        if st.form_submit_button("➕ Add Device"):
            st.session_state.devices.append({
                "device_name": device_name,
                "device_type": selected_type,
                "location": location,
                "ONT_PORT": ont_port if selected_type == "ONT" else "",
                "ONT_PROFILE_ID": ont_profile_id if selected_type == "ONT" else "",
                "ONT_MOMENTUM_PASSWORD": "NO VALUE"
            })
            st.success(f"{device_name} added to list ✅")

    # 5. Show added devices
    if st.session_state.devices:
        st.markdown("### Devices Selected:")
        for i, d in enumerate(st.session_state.devices):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"🔹 {d['device_name']} → {d['device_type']} @ {d['location']}")
                if d["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE")
            with col2:
                if st.button("🗑️ Remove", key=f"remove_{i}"):
                    st.session_state.devices.pop(i)
                    st.rerun()

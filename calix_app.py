import streamlit as st
import pandas as pd
import re
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config(page_title="Calix Inventory Import", layout="wide")
st.title("📥 Calix Inventory Import Tool")

# Session state initialization
if "devices" not in st.session_state:
    st.session_state.devices = []
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "df" not in st.session_state:
    st.session_state.df = None

# Step 1: Upload file and confirm header
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    file = st.file_uploader("Upload your .csv or .xlsx file", type=["csv", "xlsx"])
    df = None

    if file:
        try:
            # Preview first 5 rows to allow the user to select header
            df_preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
            st.write("### Preview First 5 Rows:")
            st.dataframe(df_preview.head())

            # Allow the user to select the header row
            header_row = st.radio("Which row contains the column headers? ℹ️", df_preview.index[:5], help="Choose the row that contains actual field names like Serial Number, MAC, etc.")
            if st.button("✅ Set Header Row"):
                # Load the actual file with the selected header row
                df = pd.read_csv(file, skiprows=header_row) if file.name.endswith(".csv") else pd.read_excel(file, skiprows=header_row)
                df.columns = df.columns.str.strip()  # Strip any leading/trailing spaces from column names
                st.session_state.df = df  # Save the DataFrame in session state
                st.session_state.header_confirmed = True  # Mark the header as confirmed
                st.success("✅ Step 1 completed! You can now proceed to Step 2.")  # Show confirmation
                st.session_state.header_confirmed = True  # Close this step and allow Step 2
                st.experimental_rerun()  # Refresh the app to move to Step 2
        except Exception as e:
            st.error(f"Error reading file: {e}")

# Spacer before Step 2
st.markdown("\n\n")

# Step 2: Add Devices to Convert
if st.session_state.header_confirmed:
    step2_expander = st.expander("🔧 Step 2: Add Devices to Convert", expanded=True)
    with step2_expander:
        device_name = st.text_input("Enter device model name ℹ️", help="Found in the Description column of your file")
        load_defaults = st.button("🔍 Look Up Device")

        # Default values
        default_ont_port = ""
        default_profile_id = ""
        device_found = False

        if load_defaults and device_name:
            # Normalize the device name to uppercase to match the keys in the mapping
            device_name = device_name.upper()

            if device_name in device_profile_name_map:
                device_found = True
                device_type = device_profile_name_map[device_name]
                template = device_numbers_template_map.get(device_name, "")
                # Extract default ONT_PORT and ONT_PROFILE_ID from the template
                if device_type == "ONT" and template:
                    match_port = re.search(r"ONT_PORT=([^|]*)", template)
                    match_profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                    default_ont_port = match_port.group(1) if match_port else ""
                    default_profile_id = match_profile.group(1) if match_profile else ""

        # Allow customization of ONT_PORT and ONT_PROFILE_ID
        custom_ont_port = st.text_input("ONT_PORT ℹ️", value=default_ont_port, help="The interface this ONT uses to connect (e.g., G1 or x1)") if device_found else None
        custom_profile_id = st.text_input("ONT_PROFILE_ID ℹ️", value=default_profile_id, help="Provisioning profile used in your system") if device_found else None

        # Add Device
        add_device = st.button("➕ Add Device")
        if add_device and device_name:
            # Capture the current values of ONT_PORT and ONT_PROFILE_ID without modifying them
            st.session_state.devices.append({
                "device_name": device_name.strip(),
                "ONT_PORT": custom_ont_port.strip() if custom_ont_port else default_ont_port,
                "ONT_PROFILE_ID": custom_profile_id.strip() if custom_profile_id else default_profile_id,
                "ONT_MOMENTUM_PASSWORD": "NO VALUE"
            })
            st.success(f"✅ Device {device_name} added!")

        # Show Devices Selected
        if st.session_state.devices:
            st.write("### Devices Selected:")
            for device in st.session_state.devices:
                st.write(f"🔹 {device['device_name']} → ONT @ {device['ONT_PORT']} (Profile ID: {device['ONT_PROFILE_ID']})")
                st.write(f"ONT_MOMENTUM_PASSWORD: {device['ONT_MOMENTUM_PASSWORD']}")

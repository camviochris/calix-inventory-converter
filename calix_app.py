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
            device_name = st.text_input("Enter device model name ℹ️", help="Found in the Description column of your file")
            lookup = st.form_submit_button("🔍 Look Up Device")

            data = {
                "type": "ONT",
                "port": "",
                "profile": device_name.upper(),
            }

            if lookup:
                # Case-insensitive match
                matched_key = next((k for k in device_profile_name_map if k.lower() == device_name.lower()), None)
                if matched_key:
                    mapped_profile = device_profile_name_map.get(matched_key, "ONT")
                    data["type"] = mapped_profile

                    template = device_numbers_template_map.get(matched_key, "")
                    match_port = re.search(r"ONT_PORT=([^|]*)", template)
                    match_profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                    data["port"] = match_port.group(1).strip() if match_port else ""
                    data["profile"] = match_profile.group(1).strip() if match_profile else device_name.upper()
                else:
                    st.warning("🚧 This device model name was not found in memory. You can still proceed by entering the fields manually.")

            # Device type selection with mapped default
            device_types = ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"]
            mapped_type = data.get("type", "ONT")
            friendly_type = (
                "ROUTER" if "ROUTER" in mapped_type else
                "MESH" if "MESH" in mapped_type else
                "SFP" if "SFP" in mapped_type else
                "ENDPOINT" if "ENDPOINT" in mapped_type else
                "ONT"
            )
            device_type = st.selectbox(
                "What type of device is this?",
                device_types,
                index=device_types.index(friendly_type),
                help="Make sure this matches how your system provisions this device"
            )

            if lookup and friendly_type != device_type:
                st.warning(f"⚠️ This device is typically identified as `{friendly_type}`. You selected `{device_type}`. If this is correct, ensure your provisioning is properly configured.")

            location = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom..."])
            if location == "Custom...":
                location = st.text_input("Enter custom location")
                st.warning("⚠️ This must match the Camvio inventory location **exactly**, including case and spelling.")

            custom_ont_port = ""
            custom_profile_id = ""
            if device_type == "ONT":
                st.markdown("#### Customize ONT Settings (required)")
                custom_ont_port = st.text_input("ONT_PORT", value=data.get("port", ""))
                custom_profile_id = st.text_input("ONT_PROFILE_ID", value=data.get("profile", device_name.upper()))

            add_device = st.form_submit_button("➕ Add Device")
            if add_device:
                st.session_state.devices.append({
                    "device_name": device_name,
                    "device_type": device_type,
                    "location": location,
                    "ONT_PORT": custom_ont_port.strip() if device_type == "ONT" else "",
                    "ONT_PROFILE_ID": custom_profile_id.strip().upper() if device_type == "ONT" else "",
                    "ONT_MOMENTUM_PASSWORD": "NO VALUE"
                })
                st.success(f"{device_name} added to list ✅")

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
                        st.rerun() # Replace if needed

# End of script

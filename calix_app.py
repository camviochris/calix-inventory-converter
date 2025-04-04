import streamlit as st
import pandas as pd
import re
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config(page_title="Calix Inventory Import Tool", layout="wide")
st.title("📥 Calix Inventory Import Tool")

# --- SESSION STATE INIT ---
if "df" not in st.session_state:
    st.session_state.df = None
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "devices" not in st.session_state:
    st.session_state.devices = []
if "device_name_input" not in st.session_state:
    st.session_state.device_name_input = ""
if "device_type_input" not in st.session_state:
    st.session_state.device_type_input = "ONT"
if "location_input" not in st.session_state:
    st.session_state.location_input = "WAREHOUSE"
if "custom_location" not in st.session_state:
    st.session_state.custom_location = ""
if "ont_port_input" not in st.session_state:
    st.session_state.ont_port_input = ""
if "ont_profile_id_input" not in st.session_state:
    st.session_state.ont_profile_id_input = ""
if "lookup_warning" not in st.session_state:
    st.session_state.lookup_warning = ""
if "company_name_input" not in st.session_state:
    st.session_state.company_name_input = ""

# --- UI to backend mapping ---
ui_to_backend = {
    "ONT": "ONT",
    "ROUTER": "CX_ROUTER",
    "MESH": "CX_MESH",
    "SFP": "CX_SFP",
    "ENDPOINT": "GAM_COAX_ENDPOINT"
}

# --- STEP 1: Upload & Set Header ---
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    file = st.file_uploader("Upload .csv or .xlsx file", type=["csv", "xlsx"])
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

# --- STEP 2: Add Devices ---
if st.session_state.header_confirmed:
    with st.expander("🛠️ Step 2: Add Devices to Convert", expanded=True):
        st.text_input("Enter device model name", key="device_name_input")
        st.selectbox("What type of device is this?", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"], key="device_type_input")
        st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom"], key="location_input")

        if st.session_state.location_input == "Custom":
            st.text_input("Enter custom location (must match Camvio exactly)", key="custom_location")
            st.warning("⚠️ Custom locations must match Camvio inventory location **exactly**, including spelling, case, and spacing.")

        if st.button("🔍 Look Up Device"):
            model_upper = st.session_state.device_name_input.strip().upper()
            matched_key = next((k for k in device_profile_name_map if k.upper() == model_upper), None)
            template = device_numbers_template_map.get(matched_key) if matched_key else ""

            if matched_key:
                expected_backend_type = device_profile_name_map.get(matched_key)
                selected_ui_type = st.session_state.device_type_input
                selected_backend_type = ui_to_backend.get(selected_ui_type, selected_ui_type)

                # Only warn if there's a real mismatch
                if expected_backend_type != selected_backend_type:
                    st.session_state.lookup_warning = (
                        f"⚠️ This device is typically mapped as `{expected_backend_type}`. "
                        f"You selected `{selected_backend_type}`.\n\n"
                        f"{'Provisioning may fail if this is incorrect.' if expected_backend_type == 'ONT' else 'Ensure your system supports this mapping.'}"
                    )
                else:
                    st.session_state.lookup_warning = ""

                port_match = re.search(r"ONT_PORT=([^|]*)", template)
                profile_match = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                st.session_state.ont_port_input = port_match.group(1) if port_match else ""
                st.session_state.ont_profile_id_input = profile_match.group(1).upper() if profile_match else model_upper
            else:
                st.session_state.lookup_warning = (
                    "🚧 This device was not found in memory. If it's an ONT, provide `ONT_PORT` and `ONT_PROFILE_ID` manually.\n"
                    "Ensure this device is added to your Camvio provisioning system to avoid issues."
                )

        if st.session_state.device_type_input == "ONT":
            st.text_input("ONT_PORT", value=st.session_state.ont_port_input, key="ont_port_input")
            st.text_input("ONT_PROFILE_ID", value=st.session_state.ont_profile_id_input, key="ont_profile_id_input")

        if st.session_state.lookup_warning:
            st.warning(st.session_state.lookup_warning)

        if st.button("➕ Add Device"):
            location = (
                st.session_state.custom_location.strip()
                if st.session_state.location_input == "Custom"
                else st.session_state.location_input
            )
            device = {
                "device_name": st.session_state.device_name_input.strip(),
                "device_type": st.session_state.device_type_input,
                "location": location,
                "ONT_PORT": st.session_state.ont_port_input.strip() if st.session_state.device_type_input == "ONT" else "",
                "ONT_PROFILE_ID": st.session_state.ont_profile_id_input.strip().upper() if st.session_state.device_type_input == "ONT" else "",
                "ONT_MOMENTUM_PASSWORD": "NO VALUE"
            }
            st.session_state.devices.append(device)

        if st.session_state.devices:
            st.subheader("Devices Selected:")
            for i, d in enumerate(st.session_state.devices):
                st.markdown(f"🔹 **{d['device_name']}** → _{d['device_type']}_ → `{d['location']}`")
                if d["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE", language="text")
                if st.button(f"❌ Remove", key=f"remove_{i}"):
                    st.session_state.devices.pop(i)
                    st.rerun()

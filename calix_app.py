import streamlit as st
import pandas as pd
import re
import datetime
import io
from mappings import device_profile_name_map, device_numbers_template_map

# Page Config
st.set_page_config(page_title="Calix Inventory Import Tool", layout="wide")
st.title("📥 Calix Inventory Import Tool")
st.caption("This tool processes everything in-memory and does **not** store any data. Secure and session-based.")

# Session State Init
if "df" not in st.session_state:
    st.session_state.df = None
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "devices" not in st.session_state:
    st.session_state.devices = []
st.session_state.setdefault("device_name_input", "")
st.session_state.setdefault("device_type_input", "ONT")
st.session_state.setdefault("location_input", "WAREHOUSE")
st.session_state.setdefault("custom_location", "")
st.session_state.setdefault("ont_port_input", "")
st.session_state.setdefault("ont_profile_id_input", "")
st.session_state.setdefault("lookup_warning", "")
st.session_state.setdefault("company_name_input", "")

# Button: Start Over
with st.sidebar:
    if st.button("🔄 Start Over"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()

# Mapping
ui_to_backend = {
    "ONT": "ONT",
    "ROUTER": "CX_ROUTER",
    "MESH": "CX_MESH",
    "SFP": "CX_SFP",
    "ENDPOINT": "GAM_COAX_ENDPOINT"
}

# STEP 1: Upload File
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    file = st.file_uploader("Upload .csv or .xlsx", type=["csv", "xlsx"])
    if file:
        try:
            preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
            st.write("### Preview First 5 Rows")
            st.dataframe(preview.head())
            header_row = st.radio("Select the row that contains column headers", preview.index[:5])
            if st.button("✅ Set Header Row"):
                df = pd.read_csv(file, skiprows=header_row) if file.name.endswith(".csv") else pd.read_excel(file, skiprows=header_row)
                df.columns = df.columns.str.strip()
                st.session_state.df = df
                st.session_state.header_confirmed = True
                st.experimental_rerun()
        except Exception as e:
            st.error(f"Error reading file: {e}")

# STEP 2: Add Devices
if st.session_state.header_confirmed:
    with st.expander("🔧 Step 2: Add Devices", expanded=True):
        st.subheader("Add Devices to Convert")
        st.text_input("Device Model Name", key="device_name_input", help="Enter the model name shown in your spreadsheet's Description column")
        st.selectbox("Device Type", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"], key="device_type_input", help="This determines the profile used for export")
        st.selectbox("Storage Location", ["WAREHOUSE", "Custom"], key="location_input")

        if st.session_state.location_input == "Custom":
            st.text_input("Enter Custom Location", key="custom_location")
            st.warning("⚠️ Must match location name in Camvio exactly (case/spelling/spacing).")

        if st.button("🔍 Look Up Device"):
            model_input = st.session_state.device_name_input.strip().upper()
            matched_key = next((k for k in device_profile_name_map if k.upper() == model_input), None)
            template = device_numbers_template_map.get(matched_key, "")

            if matched_key:
                expected = device_profile_name_map[matched_key]
                selected_ui = st.session_state.device_type_input
                selected_backend = ui_to_backend.get(selected_ui, selected_ui)
                if expected != selected_backend:
                    st.session_state.lookup_warning = (
                        f"⚠️ This device is typically mapped as `{expected}`. You selected `{selected_backend}`."
                        f"{' Since this is an ONT, provisioning may be affected. Please verify.' if expected == 'ONT' else ''}"
                    )
                else:
                    st.session_state.lookup_warning = ""

                port = re.search(r"ONT_PORT=([^|]*)", template)
                profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                st.session_state.ont_port_input = port.group(1) if port else ""
                st.session_state.ont_profile_id_input = profile.group(1).upper() if profile else model_input
            else:
                st.session_state.lookup_warning = (
                    "🚧 Device not found in memory. If this is an ONT, provide ONT_PORT and ONT_PROFILE_ID manually. "
                    "Ensure your provisioning system supports this model."
                )

        if st.session_state.device_type_input == "ONT":
            st.text_input("ONT_PORT", value=st.session_state.ont_port_input, key="ont_port_input")
            st.text_input("ONT_PROFILE_ID", value=st.session_state.ont_profile_id_input, key="ont_profile_id_input")

        if st.session_state.lookup_warning:
            st.warning(st.session_state.lookup_warning)

        if st.button("➕ Add Device"):
            location = st.session_state.custom_location.strip() if st.session_state.location_input == "Custom" else st.session_state.location_input
            st.session_state.devices.append({
                "device_name": st.session_state.device_name_input.strip(),
                "device_type": st.session_state.device_type_input,
                "location": location,
                "ONT_PORT": st.session_state.ont_port_input.strip() if st.session_state.device_type_input == "ONT" else "",
                "ONT_PROFILE_ID": st.session_state.ont_profile_id_input.strip().upper() if st.session_state.device_type_input == "ONT" else "",
                "ONT_MOMENTUM_PASSWORD": "NO VALUE"
            })

        if st.session_state.devices:
            st.subheader("Devices Selected")
            for i, d in enumerate(st.session_state.devices):
                st.markdown(f"🔹 **{d['device_name']}** → _{d['device_type']}_ @ `{d['location']}`")
                if d["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE")
                if st.button(f"❌ Remove", key=f"remove_{i}"):
                    st.session_state.devices.pop(i)
                    st.experimental_rerun()

# Footer
st.markdown("---")
st.markdown("<div style='text-align:right; font-size:0.8em; color:gray;'>Last updated: 2025-04-04 • Rev: v3.20</div>", unsafe_allow_html=True)

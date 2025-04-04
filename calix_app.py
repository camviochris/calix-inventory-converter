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
if "ont_port_input" not in st.session_state:
    st.session_state.ont_port_input = ""
if "ont_profile_id_input" not in st.session_state:
    st.session_state.ont_profile_id_input = ""
if "lookup_warning" not in st.session_state:
    st.session_state.lookup_warning = ""

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

        # Look Up Device
        if st.button("🔍 Look Up Device"):
            model_upper = st.session_state.device_name_input.strip().upper()
            mapped_type = device_profile_name_map.get(model_upper)
            template = device_numbers_template_map.get(model_upper)

            # Preserve user choice but warn if mismatch
            if mapped_type and mapped_type != st.session_state.device_type_input:
                st.session_state.lookup_warning = (
                    f"⚠️ This device is typically mapped as `{mapped_type}`. "
                    f"You selected `{st.session_state.device_type_input}`. "
                    f"Ensure your provisioning system is configured accordingly."
                )
            else:
                st.session_state.lookup_warning = ""

            if template and "ONT_PORT" in template:
                port_match = re.search(r"ONT_PORT=([^|]*)", template)
                profile_match = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                if port_match:
                    st.session_state.ont_port_input = port_match.group(1)
                if profile_match:
                    st.session_state.ont_profile_id_input = profile_match.group(1)
            else:
                st.session_state.ont_port_input = ""
                st.session_state.ont_profile_id_input = st.session_state.device_name_input.strip().upper()

        if st.session_state.device_type_input == "ONT":
            st.text_input("ONT_PORT", value=st.session_state.ont_port_input, key="ont_port_input")
            st.text_input("ONT_PROFILE_ID", value=st.session_state.ont_profile_id_input, key="ont_profile_id_input")

        if st.session_state.lookup_warning:
            st.warning(st.session_state.lookup_warning)

        # Add Device
        if st.button("➕ Add Device"):
            device = {
                "device_name": st.session_state.device_name_input.strip(),
                "device_type": st.session_state.device_type_input,
                "location": st.session_state.location_input.strip(),
                "ONT_PORT": st.session_state.ont_port_input.strip() if st.session_state.device_type_input == "ONT" else "",
                "ONT_PROFILE_ID": st.session_state.ont_profile_id_input.strip() if st.session_state.device_type_input == "ONT" else "",
                "ONT_MOMENTUM_PASSWORD": "NO VALUE"
            }
            st.session_state.devices.append(device)

        # Devices Selected
        if st.session_state.devices:
            st.subheader("Devices Selected:")
            for i, d in enumerate(st.session_state.devices):
                st.markdown(f"🔹 **{d['device_name']}** → {d['device_type']} @ {d['location']}")
                if d["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE", language="text")
                if st.button(f"❌ Remove", key=f"remove_{i}"):
                    st.session_state.devices.pop(i)
                    st.rerun()

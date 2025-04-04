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
            st.markdown("### ➕ Add Device")

            # Input device model and type
            device_name = st.text_input("Enter device model name ℹ️", help="Match what's found in the Description column")
            selected_type = st.selectbox("What type of device is this?", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"])

            # Look up from mapping.py
            if st.form_submit_button("🔍 Look Up Device"):
                st.session_state.lookup_result = {
                    "device_name": device_name,
                    "device_type": device_profile_name_map.get(device_name.upper(), selected_type),
                    "template": device_numbers_template_map.get(device_name.upper(), "")
                }

            # Default values from lookup (if available)
            data = st.session_state.get("lookup_result", {})
            default_type = data.get("device_type", selected_type)
            template = data.get("template", "")
            default_port = re.search(r"ONT_PORT=([^|]*)", template)
            default_profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)

            default_port = default_port.group(1) if default_port else ""
            default_profile = default_profile.group(1).upper() if default_profile else device_name.upper()

            # Show ONT-specific inputs
            if selected_type == "ONT":
                ont_port = st.text_input("ONT_PORT", value=default_port)
                ont_profile = st.text_input("ONT_PROFILE_ID", value=default_profile)
            else:
                ont_port, ont_profile = "", ""

            # Location selection with custom input
            location = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom"])
            if location == "Custom":
                location = st.text_input("Enter custom location (must match Camvio exactly)")
                st.warning("⚠️ This must match Camvio Web **exactly** or provisioning will fail.")

            # Warning if type mismatch with mapping
            expected_type = device_profile_name_map.get(device_name.upper(), "")
            mapped_type_clean = expected_type.replace("CX_", "") if "CX_" in expected_type else expected_type
            if expected_type and mapped_type_clean != selected_type:
                st.warning(
                    f"⚠️ This device is typically mapped as `{mapped_type_clean}`. "
                    f"You selected `{selected_type}`. Make sure your provisioning is properly configured."
                )

            # Add the device to session
            if st.form_submit_button("➕ Add Device"):
                st.session_state.devices.append({
                    "device_name": device_name,
                    "device_type": selected_type,
                    "location": location,
                    "ONT_PORT": ont_port,
                    "ONT_PROFILE_ID": ont_profile,
                    "ONT_MOMENTUM_PASSWORD": "NO VALUE"
                })
                st.success("✅ Device added successfully!")
                st.rerun()


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

# --- Step 3: Export (UI only for now) ---
if st.session_state.df is not None and st.session_state.devices:
    with st.expander("📤 Step 3: Export File", expanded=True):
        st.session_state.company_name = st.text_input("Enter your company name")
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        file_name = f"{st.session_state.company_name}_{today_str}.csv" if st.session_state.company_name else "output.csv"

        st.markdown("### 📦 Export Overview")
        for d in st.session_state.devices:
            st.markdown(f"- **{d['device_name']}** → {d['device_type']} @ {d['location']}")

        st.markdown("🔔 Click export when ready to generate your output file.")
        if st.button("📥 Export & Download File"):
            output = io.StringIO()
            output.write("device_profile,device_name,device_numbers,inventory_location,inventory_status\n")

            df = st.session_state.df
            desc_col = next((col for col in df.columns if "description" in col.lower()), None)
            mac_col = next((col for col in df.columns if "mac" in col.lower()), None)
            sn_col = next((col for col in df.columns if "serial" in col.lower() or "sn" in col.lower()), None)
            fsan_col = next((col for col in df.columns if "fsan" in col.lower()), None)

            for device in st.session_state.devices:
                device_name = device["device_name"]
                matches = df[df[desc_col].astype(str).str.contains(device_name, case=False, na=False)]
                profile_type = device_profile_name_map.get(device_name.upper(), f"CX_{device['device_type']}")

                for _, row in matches.iterrows():
                    mac = str(row.get(mac_col, "NO VALUE")).strip()
                    sn = str(row.get(sn_col, "NO VALUE")).strip()
                    fsan = str(row.get(fsan_col, "NO VALUE")).strip()

                    numbers = f"MAC={mac}|SN={sn}|FSAN={fsan}"
                    if profile_type == "ONT":
                        numbers = f"MAC={mac}|SN={sn}|ONT_FSAN={fsan}|ONT_ID=NO VALUE|ONT_NODENAME=NO VALUE|ONT_PORT={device['ONT_PORT']}|ONT_PROFILE_ID={device['ONT_PROFILE_ID']}|ONT_MOMENTUM_PASSWORD={device['ONT_MOMENTUM_PASSWORD']}"

                    output.write(f"{profile_type},{device_name},{numbers},{device['location']},UNASSIGNED\n")

            st.download_button("⬇️ Download File", data=output.getvalue(), file_name=file_name, mime="text/csv")

# --- Footer ---
st.markdown("---")
st.markdown("<div style='text-align: right; font-size: 0.75em; color: gray;'>Last updated: 2025-04-04 • Rev: v3.0</div>", unsafe_allow_html=True)

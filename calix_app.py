from datetime import datetime
import streamlit as st
import pandas as pd
import io
import re
from mappings import device_profile_name_map

# --- Initialize session state ---
if "devices" not in st.session_state:
    st.session_state.devices = []
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "df" not in st.session_state:
    st.session_state.df = None
if "company_name" not in st.session_state:
    st.session_state.company_name = ""

# --- Title and Help Section ---
st.set_page_config(page_title="Calix Inventory Converter", layout="wide")
st.title("📥 Calix Inventory Converter")

with st.expander("❓ How to Use This Tool", expanded=False):
    st.markdown("""
This tool converts inventory files for import into your provisioning system.

**Steps to Use:**
1. Upload a `.csv` or `.xlsx` file.
2. Select which row has your headers (e.g., MAC, Serial Number, Description).
3. Identify devices in your file and map them as ONT, Router, SFP, etc.
4. Customize ONT provisioning values if needed.
5. Export your file in the correct format.

**Important:**
- ONT devices must have correct `ONT_PORT` and `ONT_PROFILE_ID` settings.
- Custom locations must **exactly** match spelling/case in your system.
- File names are saved locally and nothing is stored on the cloud.

The final file will be named like: `Company_YYYYMMDD_HHMMSS.csv`
""")

# --- Reset Button ---
if st.button("🔄 Reset All"):
    st.session_state.devices = []
    st.session_state.header_confirmed = False
    st.session_state.df = None
    st.rerun()

# --- Step 1: Upload File and Confirm Header Row ---
with st.expander("📁 Step 1: Upload File and Set Header Row", expanded=not st.session_state.header_confirmed):
    file = st.file_uploader("Upload your inventory file", type=["csv", "xlsx"])
    if file:
        preview_df = pd.read_csv(file, header=None) if file.name.endswith("csv") else pd.read_excel(file, header=None)
        st.write("🔎 **Preview** - First 5 Rows")
        st.dataframe(preview_df.head())
        header_row = st.number_input("Select the row number containing headers", min_value=0, max_value=4, value=0, step=1)
        if st.button("✅ Set Header Row"):
            df = pd.read_csv(file, skiprows=header_row) if file.name.endswith("csv") else pd.read_excel(file, skiprows=header_row)
            df.columns = df.columns.str.strip()
            st.session_state.df = df
            st.session_state.header_confirmed = True
            st.success("✅ Header row confirmed.")
            st.rerun()

# --- Step 2: Add Devices ---
if st.session_state.header_confirmed:
    with st.expander("🛠️ Step 2: Add Devices to Convert", expanded=True):
        with st.form("device_form", clear_on_submit=True):
            device_name = st.text_input("Enter Device Model Name").upper().strip()
            device_type = st.selectbox("What type of device is this?", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"])
            location_choice = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom"])
            location = "WAREHOUSE"
            if location_choice == "Custom":
                location = st.text_input("Enter Custom Location").strip()
                st.warning("⚠️ Custom location must match Camvio EXACTLY (case-sensitive).")

            mapped_type = device_profile_name_map.get(device_name)
            if mapped_type:
                mapped_type_clean = mapped_type.replace("CX_", "")
                if mapped_type_clean != device_type:
                    st.warning(f"⚠️ This device is typically mapped as `{mapped_type_clean}`. You selected `{device_type}`. Ensure your provisioning system is configured accordingly.")
            else:
                if device_type == "ONT":
                    st.warning("🚧 This device isn't found in our standard list. If this is a new ONT, verify that your provisioning system supports it.")

            ont_port = st.text_input("ONT_PORT", value="") if device_type == "ONT" else ""
            ont_profile = st.text_input("ONT_PROFILE_ID", value=device_name) if device_type == "ONT" else ""

            if st.form_submit_button("➕ Add Device"):
                st.session_state.devices.append({
                    "device_name": device_name,
                    "device_type": device_type,
                    "location": location,
                    "ONT_PORT": ont_port,
                    "ONT_PROFILE_ID": ont_profile
                })
                st.success(f"{device_name} added.")

        if st.session_state.devices:
            st.markdown("### ✅ Devices Selected")
            for idx, device in enumerate(st.session_state.devices):
                st.markdown(f"**{device['device_name']}** ({device['device_type']}) → `{device['location']}`")
                if device["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {device['ONT_PORT']}\nONT_PROFILE_ID: {device['ONT_PROFILE_ID']}")
                if st.button("🗑️ Remove", key=f"remove_{idx}"):
                    st.session_state.devices.pop(idx)
                    st.rerun()

# --- Step 3: Export CSV ---
if st.session_state.devices and "df" in st.session_state:
    with st.expander("📦 Step 3: Export File", expanded=True):
        st.session_state.company_name = st.text_input("Company Name", value=st.session_state.company_name)
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        export_name = f"{st.session_state.company_name}_{timestamp}.csv" if st.session_state.company_name else f"inventory_export_{timestamp}.csv"

        desc_col = next((col for col in st.session_state.df.columns if 'description' in col.lower()), None)
        mac_col = next((col for col in st.session_state.df.columns if 'mac' in col.lower()), None)
        sn_col = next((col for col in st.session_state.df.columns if 'serial' in col.lower() or col.lower() == 'sn'), None)
        fsan_col = next((col for col in st.session_state.df.columns if 'fsan' in col.lower()), None)

        fsan_label_map = {
            "ONT": "ONT_FSAN",
            "CX_ROUTER": "ROUTER_FSAN",
            "CX_MESH": "MESH_FSAN",
            "CX_SFP": "SIP_FSAN"
        }

        output = io.StringIO()
        output.write("device_profile,device_name,device_numbers,inventory_location,inventory_status\n")

        for device in st.session_state.devices:
            name = device["device_name"]
            dtype = device["device_type"]
            profile = device_profile_name_map.get(name.upper(), f"CX_{dtype}")
            fsan_label = fsan_label_map.get(profile, "FSAN")

            matches = st.session_state.df[
                st.session_state.df[desc_col].astype(str).str.contains(name, case=False, na=False)
            ]

            for _, row in matches.iterrows():
                mac = str(row.get(mac_col, "NO VALUE")).strip()
                sn = str(row.get(sn_col, "NO VALUE")).strip()
                fsan = str(row.get(fsan_col, "NO VALUE")).strip()

                if profile == "ONT":
                    device_numbers = (
                        f"MAC={mac}|SN={sn}|ONT_FSAN={fsan}|ONT_ID=NO VALUE|"
                        f"ONT_NODENAME=NO VALUE|ONT_PORT={device['ONT_PORT']}|"
                        f"ONT_PROFILE_ID={device['ONT_PROFILE_ID']}|ONT_MOMENTUM_PASSWORD=NO VALUE"
                    )
                elif profile == "GAM_COAX_ENDPOINT":
                    device_numbers = f"MAC={mac}|SN={sn}"
                else:
                    device_numbers = f"MAC={mac}|SN={sn}|{fsan_label}={fsan}"

                output.write(f"{profile},{name},{device_numbers},{device['location']},UNASSIGNED\n")

        st.download_button("⬇️ Export & Download File", data=output.getvalue(), file_name=export_name, mime="text/csv")
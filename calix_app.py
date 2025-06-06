from datetime import datetime
import streamlit as st
import pandas as pd
import io
import re
from mappings import device_profile_name_map, device_numbers_template_map

# --- Initialize session state ---
if "devices" not in st.session_state:
    st.session_state.devices = []
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "df" not in st.session_state:
    st.session_state.df = None
if "company_name" not in st.session_state:
    st.session_state.company_name = ""
if "custom_ont_port" not in st.session_state:
    st.session_state.custom_ont_port = ""
if "custom_profile_id" not in st.session_state:
    st.session_state.custom_profile_id = ""

# --- Title and Help Section ---
st.set_page_config(page_title="Calix Inventory Converter", layout="wide")
st.title("📅 Calix Inventory Converter")

with st.expander("❓ How to Use This Tool", expanded=False):
    st.markdown("""
This tool converts inventory files for import into your provisioning system.

**Steps:**
1. Upload a `.csv` or `.xlsx` file.
2. Select the row that contains your column headers (MAC, Serial Number, FSAN, etc.).
3. Identify devices to convert by model name, assign a device type, and set inventory location.
4. For ONTs, ONT_PORT and ONT_PROFILE_ID must be provided or defaulted.
5. Export the converted file. The file will be named `Company_YYYYMMDD_HHMMSS.csv`.

⚠️ *Custom locations must match exactly what is used in Camvio.*
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
    desc_col = next((col for col in st.session_state.df.columns if 'description' in col.lower()), None)
    mac_col = next((col for col in st.session_state.df.columns if 'mac' in col.lower()), None)
    sn_col = next((col for col in st.session_state.df.columns if 'serial' in col.lower() or col.lower() == 'sn'), None)
    fsan_col = next((col for col in st.session_state.df.columns if 'fsan' in col.lower()), None)

    if not desc_col:
        st.error("❌ Could not detect a 'Description' column. Please verify your header row selection.")
        st.stop()

    with st.expander("🛠️ Step 2: Add Devices to Convert", expanded=True):
        with st.form("device_form"):
            model_name = st.text_input("Enter Model Name (as found in import file)").strip().upper()
            camvio_item_name = st.selectbox("Select Camvio Item Name", options=sorted(device_profile_name_map.keys()))
            device_type = st.selectbox("What type of device is this?", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"])
            location_type = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom"])
            location = "WAREHOUSE"
            if location_type == "Custom":
                location = st.text_input("Enter Custom Location").strip()
                st.warning("⚠️ Custom location must match Camvio EXACTLY (case-sensitive).")

            # Checkbox to exclude MAC and SN
            exclude_mac_sn = st.checkbox("Check to exclude MAC & SN from device_numbers output.")

            if st.form_submit_button("🔍 Look Up Device"):
                template = device_numbers_template_map.get(camvio_item_name.upper())
                mapped_type = device_profile_name_map.get(camvio_item_name.upper())

                if template and mapped_type:
                    st.session_state.custom_ont_port = re.search(r"ONT_PORT=([^|]*)", template).group(1) if "ONT_PORT=" in template else ""
                    st.session_state.custom_profile_id = re.search(r"ONT_PROFILE_ID=([^|]*)", template).group(1).upper() if "ONT_PROFILE_ID=" in template else ""
                    st.rerun()
                else:
                    st.warning("🔎 This device is not in the known mapping. Proceed carefully and verify your provisioning setup.")
                    st.session_state.custom_ont_port = ""
                    st.session_state.custom_profile_id = camvio_item_name.upper()

                if mapped_type:
                    simple_type = mapped_type.replace("CX_", "")
                    if simple_type != device_type:
                        st.warning(f"⚠️ This device is typically mapped as `{simple_type}`. You selected `{device_type}`. Make sure your provisioning system supports this.")

            ont_port = ""
            ont_profile = ""
            if device_type == "ONT":
                ont_port = st.text_input("ONT_PORT", value=st.session_state.custom_ont_port)
                ont_profile = st.text_input("ONT_PROFILE_ID", value=st.session_state.custom_profile_id.upper())

            if st.form_submit_button("➕ Add Device"):
                st.session_state.devices.append({
                    "model_name": model_name,
                    "device_name": camvio_item_name,
                    "device_type": device_type,
                    "location": location,
                    "ONT_PORT": ont_port if device_type == "ONT" else "",
                    "ONT_PROFILE_ID": ont_profile if device_type == "ONT" else "",
                    "exclude_mac_sn": exclude_mac_sn
                })
                st.success(f"{camvio_item_name} added.")
                st.rerun()

    if st.session_state.devices:
        st.markdown("### ✅ Devices Selected")
        for idx, device in enumerate(st.session_state.devices):
            st.markdown(f"**{device['device_name']}** ({device['device_type']}) → `{device['location']}`")
            if device["device_type"] == "ONT":
                st.code(f"ONT_PORT: {device['ONT_PORT']}\nONT_PROFILE_ID: {device['ONT_PROFILE_ID']}")
            if device.get("exclude_mac_sn"):
                st.info("🚫 MAC & SN will be excluded from output for this device.")
            if st.button("🗑️ Remove", key=f"remove_{idx}"):
                st.session_state.devices.pop(idx)
                st.rerun()
    
# --- Step 3: Export ---
if st.session_state.devices and st.session_state.df is not None:
    with st.expander("📦 Step 3: Export File", expanded=True):
        st.session_state.company_name = st.text_input("Company Name", value=st.session_state.company_name)
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        export_name = f"{st.session_state.company_name}_{timestamp}.csv" if st.session_state.company_name else f"inventory_export_{timestamp}.csv"


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
            model = device["model_name"]
            dtype = device["device_type"]
            profile = device_profile_name_map.get(name.upper(), f"CX_{dtype}")
            fsan_label = fsan_label_map.get(profile, "FSAN")

            # Key: if user excluded MAC/SN, grab _ALT mapping
            template_key = f"{name}_ALT" if device.get("exclude_mac_sn") else name
            template = device_numbers_template_map.get(template_key.upper())

            matches = st.session_state.df[
                st.session_state.df[desc_col].astype(str).str.contains(model, case=False, na=False)
            ]

            for _, row in matches.iterrows():
                mac = str(row.get(mac_col, "NO VALUE")).strip()
                sn = str(row.get(sn_col, "NO VALUE")).strip()
                fsan = str(row.get(fsan_col, "NO VALUE")).strip()

                if template:
                    device_numbers = (
                        template.replace("<<MAC>>", mac)
                                .replace("<<SN>>", sn)
                                .replace("<<FSAN>>", fsan)
                                .replace("<<ONT_PORT>>", device.get("ONT_PORT", ""))
                                .replace("<<ONT_PROFILE_ID>>", device.get("ONT_PROFILE_ID", ""))
                    )
                else:
                    device_numbers = f"MAC={mac}|SN={sn}|{fsan_label}={fsan}"

                output.write(f"{profile},{name},{device_numbers},{device['location']},UNASSIGNED\n")

        st.download_button("⬇️ Export & Download File", data=output.getvalue(), file_name=export_name, mime="text/csv")
        st.success("✅ File is ready for download.")
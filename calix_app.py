import streamlit as st
import pandas as pd
import io
import re
import datetime
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config(page_title="Calix Inventory Converter", layout="wide")
st.title("📦 Calix Inventory Import Tool")

with st.expander("❓ How to Use This Tool", expanded=False):
    st.markdown("""
    **Welcome to the Calix Inventory Converter Tool!**

    ---
    ### 🔢 Step-by-Step Instructions:
    **Step 1: Upload File**
    - Upload a `.csv` or `.xlsx` inventory file.
    - Preview the first 5 rows and select which row contains the headers.

    **Step 2: Add Devices**
    - Enter device model name (e.g., 803G, GS4227E).
    - Choose the device type (ONT, ROUTER, MESH, etc.).
    - Click '🔍 Look Up Device' to autofill ONT settings (if known).
    - Confirm the location (e.g., WAREHOUSE or enter custom).
    - ONT-specific settings like ONT_PORT and ONT_PROFILE_ID will show for ONTs.

    **Step 3: Export File**
    - Enter your company name.
    - Click to export and download the formatted output file.

    ---
    ### ⚠️ Important Notes:
    - This app does not store any data.
    - Ensure FSAN, MAC, and SN fields are correct in the uploaded file.
    - Custom location must exactly match how it’s stored in Camvio Web.
    """)

# Session state setup
if "df" not in st.session_state:
    st.session_state.df = None
if "devices" not in st.session_state:
    st.session_state.devices = []
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False

# Step 1: Upload file
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    uploaded_file = st.file_uploader("Upload .csv or .xlsx file", type=["csv", "xlsx"])
    if uploaded_file:
        preview = pd.read_csv(uploaded_file, header=None) if uploaded_file.name.endswith("csv") else pd.read_excel(uploaded_file, header=None)
        st.write("Preview of file:")
        st.dataframe(preview.head(5))
        header_index = st.radio("Select which row contains headers", preview.index[:5])
        if st.button("✅ Set Header Row"):
            df = pd.read_csv(uploaded_file, skiprows=header_index) if uploaded_file.name.endswith("csv") else pd.read_excel(uploaded_file, skiprows=header_index)
            df.columns = df.columns.str.strip()
            st.session_state.df = df
            st.session_state.header_confirmed = True
            st.rerun()

# Step 2: Add devices
if st.session_state.header_confirmed:
    with st.expander("🔧 Step 2: Add Devices"):
        with st.form("device_form"):
            device_name = st.text_input("Device Model Name").upper()
            default_type = "ONT"
            default_port = ""
            default_profile_id = ""
            mapped_type = device_profile_name_map.get(device_name)
            template = device_numbers_template_map.get(device_name, "")

            if mapped_type:
                match_port = re.search(r"ONT_PORT=([^|]*)", template)
                match_profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                default_port = match_port.group(1) if match_port else ""
                default_profile_id = match_profile.group(1) if match_profile else ""

            device_type = st.selectbox("What type of device is this?", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"], index=0)
            if mapped_type and mapped_type.replace("CX_", "") != device_type and device_type == "ONT":
                st.warning(f"⚠️ This device is typically `{mapped_type}`, not `{device_type}`. Confirm your provisioning setup.")

            location = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom..."])
            if location == "Custom...":
                location = st.text_input("Enter custom location (must match Camvio EXACTLY)")
                st.warning("⚠️ Custom location must match exactly — spelling and case matter!")

            custom_ont_port = st.text_input("ONT_PORT", value=default_port) if device_type == "ONT" else ""
            custom_profile_id = st.text_input("ONT_PROFILE_ID", value=default_profile_id) if device_type == "ONT" else ""

            lookup_btn = st.form_submit_button("🔍 Look Up Device")
            if lookup_btn:
                st.success(f"{device_name} defaults loaded: PORT={default_port}, PROFILE_ID={default_profile_id}")

            add_btn = st.form_submit_button("➕ Add Device")
            if add_btn:
                st.session_state.devices.append({
                    "device_name": device_name,
                    "device_type": device_type,
                    "location": location,
                    "ONT_PORT": custom_ont_port.strip(),
                    "ONT_PROFILE_ID": custom_profile_id.strip().upper(),
                    "ONT_MOMENTUM_PASSWORD": "NO VALUE"
                })
                st.success(f"{device_name} added.")

    if st.session_state.devices:
        st.subheader("📋 Devices Selected")
        for i, d in enumerate(st.session_state.devices):
            st.write(f"{d['device_name']} → {d['device_type']} @ {d['location']}")
            if d["device_type"] == "ONT":
                st.code(f"ONT_PORT: {d['ONT_PORT']}, ONT_PROFILE_ID: {d['ONT_PROFILE_ID']}", language="text")
            if st.button("❌ Remove", key=f"rm_{i}"):
                st.session_state.devices.pop(i)
                st.rerun()
# Step 3: Export
if st.session_state.devices and st.session_state.df is not None:
    with st.expander("📤 Step 3: Export and Download", expanded=True):
        st.session_state.company_name = st.text_input("Enter your company name", value=st.session_state.company_name).strip()
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{st.session_state.company_name}_{now}.csv" if st.session_state.company_name else f"export_{now}.csv"

        # Count records
        desc_col = next((c for c in st.session_state.df.columns if "description" in c.lower()), None)
        if desc_col:
            st.subheader("Device Summary")
            for d in st.session_state.devices:
                count = st.session_state.df[desc_col].astype(str).str.contains(d["device_name"], case=False, na=False).sum()
                st.markdown(f"- **{d['device_name']}** ({d['device_type']}): {count} record(s)")

        if st.button("📥 Export & Download File"):
            mac_col = next((c for c in st.session_state.df.columns if "mac" in c.lower()), None)
            sn_col = next((c for c in st.session_state.df.columns if "serial" in c.lower() or c.lower() == "sn"), None)
            fsan_col = next((c for c in st.session_state.df.columns if "fsan" in c.lower()), None)

            output = io.StringIO()
            output.write("device_profile,device_name,device_numbers,inventory_location,inventory_status\n")

            for d in st.session_state.devices:
                filtered = st.session_state.df[st.session_state.df[desc_col].astype(str).str.contains(d["device_name"], case=False, na=False)]
                profile = f"CX_{d['device_type']}" if d["device_type"] != "ONT" else "ONT"
                for _, row in filtered.iterrows():
                    mac = str(row.get(mac_col, "")).strip()
                    sn = str(row.get(sn_col, "")).strip()
                    fsan = str(row.get(fsan_col, "")).strip()
                    if not mac or not sn or not fsan:
                        continue
                    if profile == "ONT":
                        numbers = f"MAC={mac}|SN={sn}|ONT_FSAN={fsan}|ONT_ID=NO VALUE|ONT_NODENAME=NO VALUE|ONT_PORT={d['ONT_PORT']}|ONT_PROFILE_ID={d['ONT_PROFILE_ID']}|ONT_MOMENTUM_PASSWORD=NO VALUE"
                    else:
                        suffix = {
                            "CX_ROUTER": "ROUTER_FSAN",
                            "CX_MESH": "MESH_FSAN",
                            "CX_SFP": "SIP_FSAN",
                            "GAM_COAX_ENDPOINT": ""
                        }.get(profile, "")
                        numbers = f"MAC={mac}|SN={sn}|{suffix}={fsan}" if suffix else f"MAC={mac}|SN={sn}"
                    output.write(f"{profile},{d['device_name']},{numbers},{d['location']},UNASSIGNED\n")

            st.download_button("⬇️ Download Converted File", data=output.getvalue(), file_name=filename, mime="text/csv")

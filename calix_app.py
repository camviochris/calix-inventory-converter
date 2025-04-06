import streamlit as st
import pandas as pd
import datetime
import io
import re
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config(page_title="Calix Inventory Import Tool", layout="wide")
st.title("📥 Calix Inventory Import Tool")
st.info("🔒 No files or data are stored. All processing is done in memory.")

# 🔄 Reset App Button
if st.button("🔄 Reset Tool"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

# 📘 Help / Instructions
with st.expander("ℹ️ How to Use This Tool", expanded=False):
    st.markdown("### Step-by-Step")
    st.markdown("1. **Upload a file** (.csv or .xlsx) and select the correct header row.")
    st.markdown("2. **Add devices**: Enter model, select device type, and set location.")
    st.markdown("3. **Export**: Enter your company name and download the formatted file.")
    st.markdown("🔁 Use the **Reset Tool** if you need to start over.")
    st.markdown("📨 Contact Camvio Support to add new devices to your system if needed.")

# 🔧 Initialize Session State
st.session_state.setdefault("devices", [])
st.session_state.setdefault("header_confirmed", False)
st.session_state.setdefault("device_lookup", {})
st.session_state.setdefault("export_complete", False)
st.session_state.setdefault("company_name", "")

# 📁 Step 1: Upload File
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    if st.session_state.header_confirmed:
        st.success("✅ Step 1 complete")

    file = st.file_uploader("Upload .csv or .xlsx", type=["csv", "xlsx"])

    if file:
        try:
            df_preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
            st.dataframe(df_preview.head())

            header_row = st.radio("Select the header row:", df_preview.index[:5])
            if st.button("✅ Set Header Row"):
                df = pd.read_csv(file, skiprows=header_row) if file.name.endswith(".csv") else pd.read_excel(file, skiprows=header_row)
                df.columns = df.columns.str.strip()
                st.session_state.df = df
                st.session_state.header_confirmed = True
                st.rerun()
        except Exception as e:
            st.error(f"Error loading file: {e}")

# 🔧 Step 2: Add Devices
if st.session_state.header_confirmed:
    with st.expander("🧩 Step 2: Add Devices to Convert", expanded=True):
        with st.form("device_form"):
            device_name = st.text_input("Enter Device Model Name").strip()
            device_name_upper = device_name.upper()

            lookup_btn = st.form_submit_button("🔍 Look Up Device")
            matched_type = device_profile_name_map.get(device_name_upper, None)
            matched_template = device_numbers_template_map.get(device_name_upper, "")

            ont_port = ""
            profile_id = ""

            if matched_template:
                ont_port_match = re.search(r"ONT_PORT=([^|]*)", matched_template)
                profile_id_match = re.search(r"ONT_PROFILE_ID=([^|]*)", matched_template)
                ont_port = ont_port_match.group(1).strip() if ont_port_match else ""
                profile_id = profile_id_match.group(1).strip().upper() if profile_id_match else device_name_upper

            device_type = st.selectbox("What type of device is this?", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"])

            if lookup_btn and matched_type and matched_type != f"CX_{device_type}" and device_type == "ONT":
                st.warning(f"⚠️ This device is typically identified as `{matched_type}`. You selected `{device_type}`. Make sure this device is configured correctly in your system.")

            location_type = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom..."])
            location = location_type
            if location_type == "Custom...":
                location = st.text_input("Enter custom location (must match Camvio EXACTLY)")
                st.warning("⚠️ Location name must match EXACTLY as shown in Camvio. Case and spelling must match.")

            if device_type == "ONT":
                ont_port = st.text_input("ONT_PORT", value=ont_port)
                profile_id = st.text_input("ONT_PROFILE_ID", value=profile_id.upper())

            if st.form_submit_button("➕ Add Device"):
                st.session_state.devices.append({
                    "device_name": device_name_upper,
                    "device_type": device_type,
                    "location": location,
                    "ONT_PORT": ont_port,
                    "ONT_PROFILE_ID": profile_id,
                    "ONT_MOMENTUM_PASSWORD": "NO VALUE"
                })
                st.success("Device added successfully!")

        # List of devices
        if st.session_state.devices:
            st.markdown("### Devices Selected:")
            for i, d in enumerate(st.session_state.devices):
                st.write(f"🔹 {d['device_name']} → {d['device_type']} @ {d['location']}")
                if d["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE")
                if st.button(f"🗑 Remove {d['device_name']}", key=f"remove_{i}"):
                    st.session_state.devices.pop(i)
                    st.rerun()

# 📦 Step 3: Export
if st.session_state.devices and "df" in st.session_state:
    with st.expander("📦 Step 3: Export and Download", expanded=True):
        st.session_state.company_name = st.text_input("Enter your company name", value=st.session_state.company_name).strip()
        today_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{st.session_state.company_name}_{today_str}.csv"

        desc_col = next((col for col in st.session_state.df.columns if 'description' in col.lower()), None)
        fsan_col = next((col for col in st.session_state.df.columns if 'fsan' in col.lower()), None)
        mac_col = next((col for col in st.session_state.df.columns if 'mac' in col.lower()), None)
        sn_col = next((col for col in st.session_state.df.columns if 'serial' in col.lower() or col.lower() == 'sn'), None)

        st.markdown("### Export Summary")
        if desc_col:
            for d in st.session_state.devices:
                count = st.session_state.df[desc_col].astype(str).str.contains(d["device_name"], case=False, na=False).sum()
                st.markdown(f"- `{d['device_name']}` → {count} matching records")

        export_btn = st.button("📤 Export & Download File")
        if export_btn:
            output = io.StringIO()
            output.write("device_profile,device_name,device_numbers,inventory_location,inventory_status\n")

            for device in st.session_state.devices:
                matches = st.session_state.df[st.session_state.df[desc_col].astype(str).str.contains(device["device_name"], case=False, na=False)]
                profile_type = f"CX_{device['device_type']}" if device['device_type'] != "ONT" else "ONT"
                template = ""

                if profile_type == "ONT":
                    template = f"MAC=<<MAC>>|SN=<<SN>>|ONT_FSAN=<<FSAN>>|ONT_ID=NO VALUE|ONT_NODENAME=NO VALUE|ONT_PORT={device['ONT_PORT']}|ONT_PROFILE_ID={device['ONT_PROFILE_ID']}|ONT_MOMENTUM_PASSWORD={device['ONT_MOMENTUM_PASSWORD']}"
                elif profile_type == "CX_ROUTER":
                    template = "MAC=<<MAC>>|SN=<<SN>>|ROUTER_FSAN=<<FSAN>>"
                elif profile_type == "CX_MESH":
                    template = "MAC=<<MAC>>|SN=<<SN>>|MESH_FSAN=<<FSAN>>"
                elif profile_type == "CX_SFP":
                    template = "MAC=<<MAC>>|SN=<<SN>>|SIP_FSAN=<<FSAN>>"
                elif profile_type == "GAM_COAX_ENDPOINT":
                    template = "MAC=<<MAC>>|SN=<<SN>>"

                for _, row in matches.iterrows():
                    mac = str(row.get(mac_col, "")).strip()
                    sn = str(row.get(sn_col, "")).strip()
                    fsan = str(row.get(fsan_col, "")).strip()
                    formatted = template.replace("<<MAC>>", mac).replace("<<SN>>", sn).replace("<<FSAN>>", fsan)
                    output.write(f"{profile_type},{device['device_name']},{formatted},{device['location']},UNASSIGNED\n")

            st.download_button("⬇️ Download File", data=output.getvalue(), file_name=filename, mime="text/csv")
            st.success("✅ File exported successfully!")

import streamlit as st
import pandas as pd
import io
import datetime
import re
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config(page_title="Calix Inventory Import Tool", layout="wide")
st.title("📥 Calix Inventory Import Tool")
st.info("🔒 This tool does not store any data. All processing is done in memory.")

# --- Clear session button ---
if st.button("🔄 Reset Tool"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- Help Section ---
with st.expander("ℹ️ How to Use This Tool", expanded=False):
    st.markdown("""
### 📋 Instructions

This tool helps you convert **Calix inventory data** into a properly formatted `.csv` file for import into Camvio systems.

---

#### 🔢 Step-by-Step

1. **Upload File**  
   Supported formats: `.csv`, `.xlsx`. Select the correct header row.  
   Example headers:
   ```
   Serial Number | MAC Address | FSAN | Item Description
   SN            | MAC         | FSAN | Product Description
   ```

2. **Add Devices**  
   Input model name (e.g., 803G), select device type, choose storage location.  
   Use **Look Up Device** to auto-fill ONT details.

3. **Export**  
   Enter company name to generate `Company_YYYYMMDD.csv`. Errors will be flagged with guidance.

---

📨 Contact Camvio Support if your provisioning setup needs new devices added.
""")

# Session initialization
if 'devices' not in st.session_state:
    st.session_state.devices = []
if 'header_confirmed' not in st.session_state:
    st.session_state.header_confirmed = False

# Step 1: Upload and set headers
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    file = st.file_uploader("Upload .csv or .xlsx", type=['csv', 'xlsx'])
    if file:
        df_preview = pd.read_csv(file, header=None) if file.name.endswith('.csv') else pd.read_excel(file, header=None)
        st.dataframe(df_preview.head())
        header_row = st.radio("Which row contains the headers?", df_preview.index[:5])
        if st.button("✅ Set Header Row"):
            df = pd.read_csv(file, skiprows=header_row) if file.name.endswith('.csv') else pd.read_excel(file, skiprows=header_row)
            df.columns = df.columns.str.strip()
            st.session_state.df = df
            st.session_state.header_confirmed = True
            st.rerun()

# Step 2: Add devices
if st.session_state.header_confirmed:
    with st.expander("🔧 Step 2: Add Devices", expanded=True):
        device_name = st.text_input("Device Model Name (e.g., 803G)")
        device_types = ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"]
        selected_type = st.selectbox("Select device type", device_types)
        location_choice = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom"])
        custom_location = ""
        if location_choice == "Custom":
            custom_location = st.text_input("Enter custom location (must match Camvio exactly)")
            st.warning("⚠️ This must match Camvio exactly including spaces and capitalization.")

        if st.button("🔍 Look Up Device"):
            matched_key = next((k for k in device_profile_name_map if k.lower() == device_name.lower()), None)
            if matched_key:
                default_type = device_profile_name_map[matched_key]
                if default_type != selected_type and default_type.replace('CX_', '') != selected_type:
                    st.warning(f"⚠️ This device is typically mapped as {default_type}. You selected {selected_type}. Ensure your provisioning system is configured accordingly.")
                template = device_numbers_template_map.get(matched_key, "")
                ont_port_match = re.search(r'ONT_PORT=([^|]+)', template)
                ont_profile_match = re.search(r'ONT_PROFILE_ID=([^|]+)', template)
                st.session_state.current_lookup = {
                    'device_name': matched_key,
                    'type': selected_type,
                    'ont_port': ont_port_match.group(1) if ont_port_match else "",
                    'ont_profile': ont_profile_match.group(1).upper() if ont_profile_match else matched_key.upper(),
                    'location': custom_location if location_choice == "Custom" else "WAREHOUSE"
                }
            else:
                if selected_type == "ONT":
                    st.warning("Device not found in memory. You may proceed by manually entering ONT details.")

        if 'current_lookup' in st.session_state:
            data = st.session_state.current_lookup
            if data['type'] == 'ONT':
                st.text_input("ONT_PORT", value=data['ont_port'], key="ont_port_field")
                st.text_input("ONT_PROFILE_ID", value=data['ont_profile'], key="ont_profile_field")
            st.write(f"**Model:** {data['device_name']}  |  **Detected Type:** {data['type']}")

            if st.button("➕ Add Device"):
                st.session_state.devices.append({
                    'device_name': data['device_name'],
                    'device_type': data['type'],
                    'location': data['location'],
                    'ONT_PORT': st.session_state.get('ont_port_field', ''),
                    'ONT_PROFILE_ID': st.session_state.get('ont_profile_field', ''),
                    'ONT_MOMENTUM_PASSWORD': 'NO VALUE'
                })
                del st.session_state['current_lookup']
                st.rerun()

        if st.session_state.devices:
            st.markdown("### Devices Selected")
            for i, d in enumerate(st.session_state.devices):
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.markdown(f"**{d['device_name']}** - {d['device_type']} → {d['location']}")
                    if d['device_type'] == 'ONT':
                        st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE", language='text')
                with col2:
                    if st.button("🗑️", key=f"remove_{i}"):
                        st.session_state.devices.pop(i)
                        st.rerun()

# Step 3: Export
if st.session_state.devices and 'df' in st.session_state:
    with st.expander("📦 Step 3: Export File", expanded=True):
        company_name = st.text_input("Enter your company name:")
        today = datetime.datetime.now().strftime("%Y%m%d")
        export_filename = f"{company_name}_{today}.csv" if company_name else "output.csv"

        desc_col = next((col for col in st.session_state.df.columns if 'description' in col.lower()), None)
        mac_col = next((col for col in st.session_state.df.columns if 'mac' in col.lower()), None)
        sn_col = next((col for col in st.session_state.df.columns if 'serial' in col.lower() or col.lower() == 'sn'), None)
        fsan_col = next((col for col in st.session_state.df.columns if 'fsan' in col.lower()), None)

        summary = []
        for d in st.session_state.devices:
            matches = st.session_state.df[desc_col].astype(str).str.contains(d['device_name'], case=False, na=False).sum()
            summary.append(f"- **{d['device_name']}** → {matches} matched records")

        st.markdown("""### 🔍 Export Summary\n""" + "\n".join(summary))

        if st.button("📤 Export & Download File") and all([desc_col, mac_col, sn_col, fsan_col]):
            output = io.StringIO()
            output.write("device_profile,device_name,device_numbers,inventory_location,inventory_status\n")
            for device in st.session_state.devices:
                profile_type = device_profile_name_map.get(device['device_name'], device['device_type'])
                template = device_numbers_template_map.get(device['device_name'], "")
                if profile_type == 'ONT':
                    template = f"MAC=<<MAC>>|SN=<<SN>>|ONT_FSAN=<<FSAN>>|ONT_ID=NO VALUE|ONT_NODENAME=NO VALUE|ONT_PORT={device['ONT_PORT']}|ONT_PROFILE_ID={device['ONT_PROFILE_ID']}|ONT_MOMENTUM_PASSWORD=NO VALUE"
                elif profile_type == 'CX_ROUTER':
                    template = "MAC=<<MAC>>|SN=<<SN>>|ROUTER_FSAN=<<FSAN>>"
                elif profile_type == 'CX_MESH':
                    template = "MAC=<<MAC>>|SN=<<SN>>|MESH_FSAN=<<FSAN>>"
                elif profile_type == 'CX_SFP':
                    template = "MAC=<<MAC>>|SN=<<SN>>|SIP_FSAN=<<FSAN>>"
                elif profile_type == 'GAM_COAX_ENDPOINT':
                    template = "MAC=<<MAC>>|SN=<<SN>>"

                matches = st.session_state.df[st.session_state.df[desc_col].astype(str).str.contains(device['device_name'], case=False, na=False)]
                for _, row in matches.iterrows():
                    line = template.replace("<<MAC>>", str(row[mac_col]).strip())\
                                   .replace("<<SN>>", str(row[sn_col]).strip())\
                                   .replace("<<FSAN>>", str(row[fsan_col]).strip())
                    output.write(f"{profile_type},{device['device_name']},{line},{device['location']},UNASSIGNED\n")

            st.download_button("⬇️ Download File", data=output.getvalue(), file_name=export_filename, mime="text/csv")

# Footer
st.markdown("---")
st.markdown("<div style='text-align:right; font-size:0.75em; color:gray;'>Last updated: 2025-04-04 • Rev: v2.95</div>", unsafe_allow_html=True)

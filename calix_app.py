import streamlit as st
import pandas as pd
import re
import io
import datetime
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config(page_title="Calix Inventory Import Tool", layout="wide")
st.title("📥 Calix Inventory Import Tool")

st.markdown("🔒 This tool processes everything in-memory and does **not** store any files or customer data.")

# -----------------------
# Session State Init
# -----------------------
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

# -----------------------
# Clear All Button
# -----------------------
with st.sidebar:
    if st.button("🔁 Start Over"):
        st.session_state.clear()
        st.rerun()

# -----------------------
# Step 1: File Upload
# -----------------------
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    uploaded_file = st.file_uploader("Upload your .csv or .xlsx file", type=["csv", "xlsx"])
    if uploaded_file:
        try:
            preview_df = pd.read_csv(uploaded_file, header=None) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file, header=None)
            st.subheader("📄 Preview First 5 Rows:")
            st.dataframe(preview_df.head())

            selected_header_row = st.radio("Select the row that contains column headers", preview_df.index[:5])
            if st.button("✅ Set Header Row"):
                df = pd.read_csv(uploaded_file, skiprows=selected_header_row) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file, skiprows=selected_header_row)
                df.columns = df.columns.str.strip()
                st.session_state.df = df
                st.session_state.header_confirmed = True
                st.rerun()
        except Exception as e:
            st.error(f"Error reading file: {e}")

# -----------------------
# Step 2: Add Devices
# -----------------------
if st.session_state.header_confirmed and st.session_state.df is not None:
    with st.expander("🔧 Step 2: Add Devices to Convert", expanded=True):
        with st.form("add_device_form", clear_on_submit=False):
            device_name = st.text_input("Enter device model name")
            device_type_options = ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"]
            device_type = st.selectbox("What type of device is this?", device_type_options)
            location = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom..."])

            # Custom location input
            if location == "Custom...":
                st.session_state.custom_location = st.text_input("Enter custom location (must match Camvio EXACTLY)")
                st.warning("⚠️ This custom location must be typed **exactly** as it appears in Camvio Web, including capitalization and spacing.")
                final_location = st.session_state.custom_location.strip()
            else:
                final_location = location

            # Defaults
            profile_data = device_profile_name_map.get(device_name.upper())
            template_data = device_numbers_template_map.get(device_name.upper(), "")
            default_port = re.search(r"ONT_PORT=([^|]*)", template_data)
            default_profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template_data)

            default_port_val = default_port.group(1) if default_port else ""
            default_profile_val = default_profile.group(1).upper() if default_profile else device_name.upper()

            # Show ONT inputs if ONT selected
            ont_port = ""
            ont_profile_id = ""
            if device_type == "ONT":
                st.markdown("#### Customize ONT Settings")
                ont_port = st.text_input("ONT_PORT", value=default_port_val)
                ont_profile_id = st.text_input("ONT_PROFILE_ID", value=default_profile_val)

            # Warnings
            if profile_data and profile_data != f"CX_{device_type}" and device_type != "ONT":
                st.warning(f"⚠️ This device is typically mapped as `{profile_data}`. You selected `{device_type}`. Ensure your provisioning system is configured accordingly.")
            if profile_data == "ONT" and device_type != "ONT":
                st.warning("⚠️ This is typically provisioned as an ONT. Selecting a different type may impact provisioning.")

            if st.form_submit_button("➕ Add Device"):
                st.session_state.devices.append({
                    "device_name": device_name,
                    "device_type": device_type,
                    "location": final_location,
                    "ONT_PORT": ont_port if device_type == "ONT" else "",
                    "ONT_PROFILE_ID": ont_profile_id if device_type == "ONT" else "",
                    "ONT_MOMENTUM_PASSWORD": "NO VALUE"
                })
                st.success(f"{device_name} added to list")

        # Devices selected preview
        if st.session_state.devices:
            st.markdown("### Devices Selected:")
            for idx, dev in enumerate(st.session_state.devices):
                st.markdown(f"- **{dev['device_name']} → {dev['device_type']} @ {dev['location']}**")
                if dev['device_type'] == "ONT":
                    st.code(f"ONT_PORT: {dev['ONT_PORT']}\nONT_PROFILE_ID: {dev['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE", language="text")
                if st.button("🗑️ Remove", key=f"remove_{idx}"):
                    st.session_state.devices.pop(idx)
                    st.rerun()

# -----------------------
# Step 3: Export & Download
# -----------------------
if st.session_state.devices:
    with st.expander("📦 Step 3: Export & Download File", expanded=True):
        st.subheader("📛 Company Info")
        company = st.text_input("Enter your company name")
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        filename = f"{company}_{today_str}.csv" if company else f"export_{today_str}.csv"

        st.subheader("📊 Summary Overview")
        desc_col = next((col for col in st.session_state.df.columns if "description" in col.lower()), None)
        if desc_col:
            for dev in st.session_state.devices:
                match_count = st.session_state.df[desc_col].astype(str).str.contains(dev["device_name"], case=False, na=False).sum()
                st.markdown(f"- **{dev['device_name']}** ({dev['device_type']}) → {dev['location']} — {match_count} match{'es' if match_count != 1 else ''}")
        else:
            st.warning("⚠️ Could not find a Description column to match against.")

        # Output file generation
        output = io.StringIO()
        output.write("device_profile,device_name,device_numbers,inventory_location,inventory_status\n")

        mac_col = next((col for col in st.session_state.df.columns if "mac" in col.lower()), None)
        sn_col = next((col for col in st.session_state.df.columns if "serial" in col.lower() or col.lower() == "sn"), None)
        fsan_col = next((col for col in st.session_state.df.columns if "fsan" in col.lower()), None)

        for dev in st.session_state.devices:
            dev_name = dev["device_name"]
            profile_type = device_profile_name_map.get(dev_name.upper(), dev["device_type"])
            template = device_numbers_template_map.get(dev_name.upper(), "MAC=<<MAC>>|SN=<<SN>>|FSAN=<<FSAN>>")

            if profile_type == "ONT":
                template = f"MAC=<<MAC>>|SN=<<SN>>|ONT_FSAN=<<FSAN>>|ONT_ID=NO VALUE|ONT_NODENAME=NO VALUE|ONT_PORT={dev['ONT_PORT']}|ONT_PROFILE_ID={dev['ONT_PROFILE_ID']}|ONT_MOMENTUM_PASSWORD=NO VALUE"
            elif profile_type == "CX_ROUTER":
                template = f"MAC=<<MAC>>|SN=<<SN>>|ROUTER_FSAN=<<FSAN>>"
            elif profile_type == "CX_MESH":
                template = f"MAC=<<MAC>>|SN=<<SN>>|MESH_FSAN=<<FSAN>>"
            elif profile_type == "CX_SFP":
                template = f"MAC=<<MAC>>|SN=<<SN>>|SIP_FSAN=<<FSAN>>"
            elif profile_type == "GAM_COAX_ENDPOINT":
                template = f"MAC=<<MAC>>|SN=<<SN>>"

            matches = st.session_state.df[st.session_state.df[desc_col].astype(str).str.contains(dev_name, case=False, na=False)]

            for _, row in matches.iterrows():
                mac = str(row.get(mac_col, "")).strip()
                sn = str(row.get(sn_col, "")).strip()
                fsan = str(row.get(fsan_col, "")).strip()
                numbers = template.replace("<<MAC>>", mac).replace("<<SN>>", sn).replace("<<FSAN>>", fsan)
                output.write(f"{profile_type},{dev_name},{numbers},{dev['location']},UNASSIGNED\n")

        st.download_button("⬇️ Export & Download File", data=output.getvalue(), file_name=filename, mime="text/csv")

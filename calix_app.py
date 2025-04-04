import streamlit as st
import pandas as pd
import datetime
import io
import re
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config(page_title="Calix Inventory Import Tool", layout="wide")
st.title("📥 Calix Inventory Import Tool")
with st.expander("ℹ️ How to Use This Tool", expanded=False):
    st.markdown("""
### 📋 Step-by-Step Instructions

1. **Upload the File You Received from Calix**
   - Upload the `.csv` or `.xlsx` inventory file that Calix provided.
   - Preview the first few rows and select which row contains the **column headers** (like Serial Number, MAC Address, etc.).

2. **Add Devices to Convert**
   - In the **Device Model Name** field, enter the model (as listed in the **Description** column of the file).
   - Select the **Type of Device** (ONT, Router, Mesh, etc.).
   - Choose where it should be stored:
     - Select `WAREHOUSE` (default) or
     - Select `Custom` and enter the exact location name from your Camvio system.
   - ⚠️ If you choose **Custom**, nothing happens right away — click `🔍 Look Up Device` to continue.
   - If the device model is recognized, default ONT settings will be filled in automatically.
   - If it's not found, you'll be able to enter the required ONT settings manually (ONT only).

3. **Export the File**
   - Enter your **company name** to be used in the final file name.
   - You'll see a breakdown of how many records match each device.
   - Click `📥 Export & Download File` to generate your converted inventory file.

---

🧠 **Important Notes**
- Only **ONTs** need provisioning info (PORT and PROFILE).
- Custom locations must **exactly match** what's configured in **Camvio Web** (including case and spacing).
- If something doesn't look right, use the **"Start Over"** button in the sidebar to reset the tool.
""")

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
            device_name = st.text_input("Enter device model name ℹ️", help="Match the format used in the Description column.")
            device_types = ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"]
            selected_type = st.selectbox("What type of device is this?", device_types)
            location = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom"])
            if location == "Custom":
                custom_location = st.text_input("Enter custom location (match Camvio exactly)")
                st.warning("⚠️ This must match Camvio Web **exactly** or it will fail.")
            else:
                custom_location = location

            lookup_clicked = st.form_submit_button("🔍 Look Up Device")

            default_port = ""
            default_profile = device_name.upper()
            if lookup_clicked and device_name:
                mapped_type = device_profile_name_map.get(device_name.upper())
                template = device_numbers_template_map.get(device_name.upper())
                if template:
                    port_match = re.search(r"ONT_PORT=([^|]*)", template)
                    profile_match = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                    default_port = port_match.group(1) if port_match else ""
                    default_profile = profile_match.group(1).upper() if profile_match else default_profile

                normalize_map = {
                    "CX_ROUTER": "ROUTER",
                    "CX_MESH": "MESH",
                    "CX_SFP": "SFP",
                    "GAM_COAX_ENDPOINT": "ENDPOINT",
                    "ONT": "ONT"
                }
                mapped_type_normalized = normalize_map.get(mapped_type, mapped_type)
                if mapped_type and mapped_type_normalized != selected_type:
                    if selected_type == "ONT":
                        st.warning(f"⚠️ This device is typically mapped as **{mapped_type_normalized}**, not **ONT**. "
                                   f"This could affect provisioning. Make sure your system supports it.")
                    else:
                        st.info(f"ℹ️ This device is typically mapped as **{mapped_type_normalized}**. You selected **{selected_type}**.")

            if selected_type == "ONT":
                ont_port = st.text_input("ONT_PORT", value=default_port)
                ont_profile = st.text_input("ONT_PROFILE_ID", value=default_profile)
            else:
                ont_port = ""
                ont_profile = ""

            if st.form_submit_button("➕ Add Device"):
                st.session_state.devices.append({
                    "device_name": device_name,
                    "device_type": selected_type,
                    "location": custom_location,
                    "ONT_PORT": ont_port,
                    "ONT_PROFILE_ID": ont_profile,
                    "ONT_MOMENTUM_PASSWORD": "NO VALUE"
                })

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

# --- Step 3: Export ---
if st.session_state.df is not None and st.session_state.devices:
    with st.expander("📤 Step 3: Export File", expanded=True):
        st.session_state.company_name = st.text_input("Enter your company name", value=st.session_state.company_name)
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        file_name = f"{st.session_state.company_name}_{today_str}.csv" if st.session_state.company_name else "output.csv"

        st.markdown("### 📦 Export Overview")
        for d in st.session_state.devices:
            df = st.session_state.df
            desc_col = next((col for col in df.columns if "description" in col.lower()), None)
            count = df[desc_col].astype(str).str.contains(d["device_name"], case=False, na=False).sum()
            st.markdown(f"- **{d['device_name']}** → {d['device_type']} @ {d['location']} — `{count}` records")

        st.markdown("---")
        if st.button("📥 Export & Download File"):
            output = io.StringIO()
            output.write("device_profile,device_name,device_numbers,inventory_location,inventory_status\n")

            df = st.session_state.df
            desc_col = next((col for col in df.columns if "description" in col.lower()), None)
            mac_col = next((col for col in df.columns if "mac" in col.lower()), None)
            sn_col = next((col for col in df.columns if "serial" in col.lower() or "sn" in col.lower()), None)
            fsan_col = next((col for col in df.columns if "fsan" in col.lower()), None)

            for device in st.session_state.devices:
                matches = df[df[desc_col].astype(str).str.contains(device["device_name"], case=False, na=False)]
                profile_type = device_profile_name_map.get(device["device_name"].upper(), f"CX_{device['device_type']}")
                for _, row in matches.iterrows():
                    mac = str(row.get(mac_col, "NO VALUE")).strip()
                    sn = str(row.get(sn_col, "NO VALUE")).strip()
                    fsan = str(row.get(fsan_col, "NO VALUE")).strip()
                    if profile_type == "ONT":
                        numbers = f"MAC={mac}|SN={sn}|ONT_FSAN={fsan}|ONT_ID=NO VALUE|ONT_NODENAME=NO VALUE|ONT_PORT={device['ONT_PORT']}|ONT_PROFILE_ID={device['ONT_PROFILE_ID']}|ONT_MOMENTUM_PASSWORD=NO VALUE"
                    elif profile_type == "CX_ROUTER":
                        numbers = f"MAC={mac}|SN={sn}|ROUTER_FSAN={fsan}"
                    elif profile_type == "CX_MESH":
                        numbers = f"MAC={mac}|SN={sn}|MESH_FSAN={fsan}"
                    elif profile_type == "CX_SFP":
                        numbers = f"MAC={mac}|SN={sn}|SIP_FSAN={fsan}"
                    elif profile_type == "GAM_COAX_ENDPOINT":
                        numbers = f"MAC={mac}|SN={sn}"
                    else:
                        numbers = f"MAC={mac}|SN={sn}|FSAN={fsan}"

                    output.write(f"{profile_type},{device['device_name']},{numbers},{device['location']},UNASSIGNED\n")

            st.download_button("⬇️ Download File", data=output.getvalue(), file_name=file_name, mime="text/csv")


# --- Footer ---
st.markdown("---")
st.markdown(
    "<div style='text-align: right; font-size: 0.75em; color: gray;'>"
    "Last updated: 2025-04-04 • Rev: v2.0"
    "</div>",
    unsafe_allow_html=True,
)

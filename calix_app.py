import streamlit as st
import pandas as pd
import io
import datetime
import re
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config(page_title="Calix Inventory Import Tool", layout="wide")
st.title("📥 Calix Inventory Import Tool")
st.info("🔒 This tool does not store any data. All processing is done in memory.")

# --- Help Section ---
with st.expander("ℹ️ How to Use This Tool", expanded=False):
    st.markdown("""
### 📋 Instructions

1. **Step 1:** Upload your `.csv` or `.xlsx` inventory file. Preview the data and select the row with column headers.
2. **Step 2:** Type your device model name, select the device type and location.
    - Click **🔍 Look Up Device** to auto-fill known ONT settings.
    - Then click **➕ Add Device** to queue it for export.
3. **Step 3:** Enter your company name and download the converted `.csv` file.

---

### ⚠️ Troubleshooting & Errors

- **App crashes after skipping Look Up Device:**  
  Always use **🔍 Look Up Device** to populate fields before **Add Device**.

- **Nothing exports or .csv is empty:**  
  Make sure your inventory file contains matching descriptions.

- **Custom Location must be exact:**  
  When using **Custom**, the location must **exactly match** how it appears in Camvio — including case and spelling.

- **ROUTER, SFP, MESH types:**  
  These don't use special provisioning fields, only ONTs do.

Need help? Contact **Camvio Support**.
""")

# --- Initialize session state ---
if "devices" not in st.session_state:
    st.session_state.devices = []
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "company_name" not in st.session_state:
    st.session_state.company_name = ""
if "lookup_result" not in st.session_state:
    st.session_state.lookup_result = {}

# --- Step 1: Upload file and confirm header ---
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    file = st.file_uploader("Upload your .csv or .xlsx file", type=["csv", "xlsx"])
    if file:
        try:
            df_preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
            st.write("### Preview First 5 Rows:")
            st.dataframe(df_preview.head())
            header_row = st.radio("Select the row number containing headers:", df_preview.index[:5])
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
            device_name = st.text_input("Enter Device Model Name")
            selected_type = st.selectbox("What type of device is this?", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"])
            location = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom"])
            if location == "Custom":
                location = st.text_input("Enter custom location (must match Camvio exactly)")
                st.warning("⚠️ Custom location must be typed EXACTLY as it appears in Camvio Web.")

            if st.form_submit_button("🔍 Look Up Device"):
                template = device_numbers_template_map.get(device_name.upper(), "")
                device_type_map = device_profile_name_map.get(device_name.upper(), selected_type)
                resolved_type = (
                    device_type_map.replace("CX_", "") if device_type_map.startswith("CX_") else device_type_map
                    if device_type_map else selected_type
                )
                st.session_state.lookup_result = {
                    "device_name": device_name,
                    "type": resolved_type,
                    "port": re.search(r"ONT_PORT=([^|]*)", template).group(1) if "ONT_PORT=" in template else "",
                    "profile": re.search(r"ONT_PROFILE_ID=([^|]*)", template).group(1).upper() if "ONT_PROFILE_ID=" in template else device_name.upper()
                }

        # After form closes, outside form scope
        data = st.session_state.lookup_result
        if data:
            st.success("✅ Device found and loaded.")
            st.write(f"**Model:** {data.get('device_name', '')}  |  **Detected Type:** {data.get('type', '')}")
            device_type = data.get("type", selected_type)
            if device_type != selected_type:
                st.warning(
                    f"⚠️ This device is typically mapped as `{device_type}`. You selected `{selected_type}`. "
                    f"Ensure your provisioning system supports this configuration."
                )
            show_port = selected_type == "ONT"
            ont_port = st.text_input("ONT_PORT", value=data.get("port", "")) if show_port else ""
            ont_profile = st.text_input("ONT_PROFILE_ID", value=data.get("profile", "")) if show_port else ""

            if st.button("➕ Add Device"):
                st.session_state.devices.append({
                    "device_name": data.get("device_name", ""),
                    "device_type": selected_type,
                    "location": location,
                    "ONT_PORT": ont_port if show_port else "",
                    "ONT_PROFILE_ID": ont_profile if show_port else "",
                    "ONT_MOMENTUM_PASSWORD": "NO VALUE"
                })
                st.success("✅ Device added.")
                st.rerun()

        if st.session_state.devices:
            st.subheader("🧾 Devices Selected:")
            for i, d in enumerate(st.session_state.devices):
                st.markdown(f"**{d['device_name']}** → `{d['device_type']}` @ `{d['location']}`")
                if d["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE")
                if st.button("🗑️ Remove", key=f"remove_{i}"):
                    st.session_state.devices.pop(i)
                    st.rerun()

# --- Step 3: Export CSV ---
if st.session_state.devices and "df" in st.session_state:
    with st.expander("📦 Step 3: Export File", expanded=True):
        st.session_state.company_name = st.text_input("Company Name", value=st.session_state.company_name)
        today = datetime.datetime.now().strftime("%Y%m%d")
        export_name = f"{st.session_state.company_name}_{today}.csv" if st.session_state.company_name else f"inventory_export_{today}.csv"

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
            match_rows = st.session_state.df[st.session_state.df[desc_col].astype(str).str.contains(name, case=False, na=False)]

            for _, row in match_rows.iterrows():
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
                    fsan_label = fsan_label_map.get(profile, "FSAN")
                    device_numbers = f"MAC={mac}|SN={sn}|{fsan_label}={fsan}"

                output.write(f"{profile},{name},{device_numbers},{device['location']},UNASSIGNED\n")

        st.download_button("⬇️ Export & Download File", data=output.getvalue(), file_name=export_name, mime="text/csv")

# --- Footer ---
st.markdown("---")
st.markdown("<div style='text-align: right; font-size: 0.75em; color: gray;'>Last updated: 2025-04-04 • Rev: v3.11</div>", unsafe_allow_html=True)

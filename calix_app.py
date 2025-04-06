import streamlit as st
import pandas as pd
import io
import datetime
import re
from mappings import device_profile_name_map, device_numbers_template_map

# Page config
st.set_page_config(page_title="Calix Inventory Import Tool", layout="wide")
st.title("📥 Calix Inventory Import Tool")

# Help Section
with st.expander("ℹ️ How to Use This Tool", expanded=False):
    st.markdown("""
### 🧾 What This Tool Does
This tool helps convert your Calix inventory spreadsheet (CSV or Excel) into a properly formatted file for Camvio.

All processing is done **in-memory** — no data is saved or stored.

---

### 🔄 Step-by-Step Instructions

1. **Upload your file**  
   - The first 5 rows are shown.  
   - Choose the row that contains headers (e.g., `Serial Number`, `MAC`, `Description`, `FSAN`).

2. **Add Devices to Convert**  
   - Type the device model name (e.g., `803G`, `GS4227E`).  
   - Select the device type (ONT, ROUTER, MESH, etc).  
   - If the device is an ONT, you’ll see `ONT_PORT` and `ONT_PROFILE_ID`.
   - Set storage location: `WAREHOUSE` or enter a custom one (**must match Camvio exactly**).

3. **Export File**  
   - Enter your company name.  
   - Review a summary of all device types and total records found.  
   - Click export to download the `.csv`.

---

### ⚠️ Important Notes

- **ONTs** need valid `ONT_PORT` and `ONT_PROFILE_ID` for provisioning.
- **Custom locations** must exactly match Camvio Web.
- If your device isn't found, enter settings manually and verify with Support.

---
""")

# Init session state
for key in ["devices", "header_confirmed", "df", "company_name"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "devices" else False if key == "header_confirmed" else "" if key == "company_name" else None

# Step 1: File upload
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    file = st.file_uploader("Upload your CSV or Excel file", type=["csv", "xlsx"])
    if file:
        try:
            df_preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
            st.dataframe(df_preview.head())

            header_row = st.radio("Select the row containing headers", df_preview.index[:5])
            if st.button("✅ Set Header Row"):
                df = pd.read_csv(file, skiprows=header_row) if file.name.endswith(".csv") else pd.read_excel(file, skiprows=header_row)
                df.columns = df.columns.str.strip()
                st.session_state.df = df
                st.session_state.header_confirmed = True
                st.rerun()
        except Exception as e:
            st.error(f"Error loading file: {e}")

# Step 2: Add devices
if st.session_state.header_confirmed and st.session_state.df is not None:
    with st.expander("🔧 Step 2: Add Devices to Convert", expanded=True):
        with st.form("device_form"):
            device_name = st.text_input("Device model name (e.g. 803G, GS4227E)").upper().strip()
            default_type = device_profile_name_map.get(device_name, "ONT")
            device_type = st.selectbox("Device type", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"], index=["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"].index(default_type))

            # Warn if mismatch
            expected_type = device_profile_name_map.get(device_name)
            if expected_type and device_type != expected_type.replace("CX_", ""):
                st.warning(f"⚠️ This device is typically mapped as {expected_type}. You selected {device_type}. Ensure your provisioning system is configured accordingly.")

            location = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom"])
            if location == "Custom":
                location = st.text_input("Enter custom location (must match Camvio exactly)")
                st.warning("⚠️ Custom location must match Camvio exactly (case and spacing).")

            # ONT-specific fields
            ont_port = ""
            ont_profile_id = ""
            if device_type == "ONT":
                template = device_numbers_template_map.get(device_name, "")
                match_port = re.search(r"ONT_PORT=([^|]*)", template)
                match_profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                ont_port = st.text_input("ONT_PORT", value=match_port.group(1) if match_port else "")
                ont_profile_id = st.text_input("ONT_PROFILE_ID", value=match_profile.group(1).upper() if match_profile else device_name.upper())

            if st.form_submit_button("➕ Add Device"):
                st.session_state.devices.append({
                    "device_name": device_name,
                    "device_type": device_type,
                    "location": location,
                    "ONT_PORT": ont_port,
                    "ONT_PROFILE_ID": ont_profile_id,
                    "ONT_MOMENTUM_PASSWORD": "NO VALUE"
                })
                st.success(f"{device_name} added successfully.")

        # Show selected
        if st.session_state.devices:
            st.markdown("### Devices Selected:")
            for i, d in enumerate(st.session_state.devices):
                st.markdown(f"- **{d['device_name']}** ({d['device_type']}) → `{d['location']}`")
                if d['device_type'] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE")
                if st.button(f"🗑️ Remove {d['device_name']}", key=f"remove_{i}"):
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

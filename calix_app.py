import streamlit as st
import pandas as pd
import re
import datetime
import io
from mappings import device_profile_name_map, device_numbers_template_map

# ========== PAGE CONFIG ==========
st.set_page_config(page_title="Calix Inventory Import Tool", layout="wide")
st.title("📥 Calix Inventory Import Tool")

# ========== SESSION STATE INIT ==========
if "df" not in st.session_state:
    st.session_state.df = None
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "devices" not in st.session_state:
    st.session_state.devices = []

# Device input state
st.session_state.setdefault("device_name_input", "")
st.session_state.setdefault("device_type_input", "ONT")
st.session_state.setdefault("location_input", "WAREHOUSE")
st.session_state.setdefault("custom_location", "")
st.session_state.setdefault("ont_port_input", "")
st.session_state.setdefault("ont_profile_id_input", "")
st.session_state.setdefault("lookup_warning", "")
st.session_state.setdefault("company_name_input", "")

# UI-to-backend mapping
ui_to_backend = {
    "ONT": "ONT",
    "ROUTER": "CX_ROUTER",
    "MESH": "CX_MESH",
    "SFP": "CX_SFP",
    "ENDPOINT": "GAM_COAX_ENDPOINT"
}

# ========== STEP 1 ==========
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    file = st.file_uploader("Upload .csv or .xlsx", type=["csv", "xlsx"])
    if file:
        try:
            preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
            st.write("### Preview First 5 Rows")
            st.dataframe(preview.head())
            header_row = st.radio("Select header row", preview.index[:5])
            if st.button("✅ Set Header Row"):
                df = pd.read_csv(file, skiprows=header_row) if file.name.endswith(".csv") else pd.read_excel(file, skiprows=header_row)
                df.columns = df.columns.str.strip()
                st.session_state.df = df
                st.session_state.header_confirmed = True
                st.rerun()
        except Exception as e:
            st.error(f"Error reading file: {e}")

# ========== STEP 2 ==========
if st.session_state.header_confirmed:
    with st.expander("🛠️ Step 2: Add Devices to Convert", expanded=True):
        st.text_input("Enter device model name", key="device_name_input")
        st.selectbox("What type of device is this?", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"], key="device_type_input")
        st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom"], key="location_input")

        if st.session_state.location_input == "Custom":
            st.text_input("Enter custom location", key="custom_location")
            st.warning("⚠️ Location must match Camvio exactly — spelling, spacing, and case-sensitive.")

        if st.button("🔍 Look Up Device"):
            model_input = st.session_state.device_name_input.strip().upper()
            matched_key = next((k for k in device_profile_name_map if k.upper() == model_input), None)
            template = device_numbers_template_map.get(matched_key, "")

            if matched_key:
                expected = device_profile_name_map[matched_key]
                selected_ui = st.session_state.device_type_input
                selected_backend = ui_to_backend.get(selected_ui, selected_ui)
                if expected != selected_backend:
                    st.session_state.lookup_warning = (
                        f"⚠️ This device is typically mapped as `{expected}`. You selected `{selected_backend}`. "
                        f"{'Since this is an ONT, provisioning may be affected. Please verify.' if expected == 'ONT' else ''}"
                    )
                else:
                    st.session_state.lookup_warning = ""

                port = re.search(r"ONT_PORT=([^|]*)", template)
                profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                st.session_state.ont_port_input = port.group(1) if port else ""
                st.session_state.ont_profile_id_input = profile.group(1).upper() if profile else model_input
            else:
                st.session_state.lookup_warning = (
                    "🚧 Device not found in memory. If this is an ONT, provide ONT_PORT and ONT_PROFILE_ID manually. "
                    "Ensure your provisioning system supports this model."
                )

        if st.session_state.device_type_input == "ONT":
            st.text_input("ONT_PORT", value=st.session_state.ont_port_input, key="ont_port_input")
            st.text_input("ONT_PROFILE_ID", value=st.session_state.ont_profile_id_input, key="ont_profile_id_input")

        if st.session_state.lookup_warning:
            st.warning(st.session_state.lookup_warning)

        if st.button("➕ Add Device"):
            location = st.session_state.custom_location.strip() if st.session_state.location_input == "Custom" else st.session_state.location_input
            st.session_state.devices.append({
                "device_name": st.session_state.device_name_input.strip(),
                "device_type": st.session_state.device_type_input,
                "location": location,
                "ONT_PORT": st.session_state.ont_port_input.strip() if st.session_state.device_type_input == "ONT" else "",
                "ONT_PROFILE_ID": st.session_state.ont_profile_id_input.strip().upper() if st.session_state.device_type_input == "ONT" else "",
                "ONT_MOMENTUM_PASSWORD": "NO VALUE"
            })

        if st.session_state.devices:
            st.subheader("Devices Selected:")
            for i, d in enumerate(st.session_state.devices):
                st.markdown(f"🔹 **{d['device_name']}** → _{d['device_type']}_ @ `{d['location']}`")
                if d["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE")
                if st.button(f"❌ Remove", key=f"remove_{i}"):
                    st.session_state.devices.pop(i)
                    st.rerun()

# ========== STEP 3 ==========
if st.session_state.df is not None and st.session_state.devices:
    with st.expander("📦 Step 3: Export and Download File", expanded=True):
        company = st.text_input("Enter your company name", key="company_name_input")
        today = datetime.datetime.now().strftime("%Y%m%d")
        filename = f"{company}_{today}.csv" if company else "calix_export.csv"

        desc_col = next((c for c in st.session_state.df.columns if "description" in c.lower()), None)

        st.subheader("📋 Export Summary")
        for d in st.session_state.devices:
            count = (
                st.session_state.df[desc_col].astype(str).str.contains(d["device_name"], case=False).sum()
                if desc_col else 0
            )
            st.markdown(
                f"- **{d['device_name']}** → `{d['device_type']}` @ `{d['location']}` → `{count}` records"
            )

        export_btn = st.button("📤 Export & Download File")
        if export_btn:
            output = io.StringIO()
            output.write("device_profile,device_name,device_numbers,inventory_location,inventory_status\n")
            error_log = io.StringIO()
            error_log.write("device_name,missing_fields,mac,sn,fsan\n")

            mac_col = next((c for c in st.session_state.df.columns if "mac" in c.lower()), None)
            sn_col = next((c for c in st.session_state.df.columns if "serial" in c.lower() or c.lower() == "sn"), None)
            fsan_col = next((c for c in st.session_state.df.columns if "fsan" in c.lower()), None)

            for device in st.session_state.devices:
                matches = st.session_state.df[st.session_state.df[desc_col].astype(str).str.contains(device["device_name"], case=False, na=False)]

                for _, row in matches.iterrows():
                    mac = str(row.get(mac_col, "")).strip()
                    sn = str(row.get(sn_col, "")).strip()
                    fsan = str(row.get(fsan_col, "")).strip()

                    missing = []
                    if not mac: missing.append("MAC")
                    if not sn: missing.append("SN")
                    if not fsan: missing.append("FSAN")

                    if missing:
                        error_log.write(f"{device['device_name']},{';'.join(missing)},{mac},{sn},{fsan}\n")
                        continue

                    profile = ui_to_backend.get(device["device_type"], device["device_type"])

                    if profile == "ONT":
                        formatted = (
                            f"MAC={mac}|SN={sn}|ONT_FSAN={fsan}|"
                            f"ONT_ID=NO VALUE|ONT_NODENAME=NO VALUE|ONT_PORT={device['ONT_PORT']}|"
                            f"ONT_PROFILE_ID={device['ONT_PROFILE_ID']}|ONT_MOMENTUM_PASSWORD=NO VALUE"
                        )
                    elif profile == "CX_ROUTER":
                        formatted = f"MAC={mac}|SN={sn}|ROUTER_FSAN={fsan}"
                    elif profile == "CX_MESH":
                        formatted = f"MAC={mac}|SN={sn}|MESH_FSAN={fsan}"
                    elif profile == "CX_SFP":
                        formatted = f"MAC={mac}|SN={sn}|SIP_FSAN={fsan}"
                    elif profile == "GAM_COAX_ENDPOINT":
                        formatted = f"MAC={mac}|SN={sn}"
                    else:
                        formatted = f"MAC={mac}|SN={sn}|FSAN={fsan}"

                    output.write(f"{profile},{device['device_name']},{formatted},{device['location']},UNASSIGNED\n")

            st.download_button("⬇️ Download Converted File", data=output.getvalue(), file_name=filename, mime="text/csv")
            error_content = error_log.getvalue()
            if "missing_fields" not in error_content:
                st.info("✅ All records exported successfully.")
            else:
                st.warning("⚠️ Some records were skipped due to missing fields.")
                st.download_button("⚠️ Download Error Log", data=error_content, file_name="error_log.csv", mime="text/csv")

# ========== FOOTER ==========
st.markdown("---")
st.markdown("<div style='text-align:right; font-size:0.8em; color:gray;'>Last updated: 2025-04-04 • Rev: v3.10</div>", unsafe_allow_html=True)

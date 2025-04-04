import streamlit as st
import pandas as pd
import io
import datetime
from mappings import device_profile_name_map, device_numbers_template_map

# Ensure session state is initialized for exporting
if "devices" not in st.session_state:
    st.session_state.devices = []
if "df" not in st.session_state:
    st.session_state.df = None
if "company_name" not in st.session_state:
    st.session_state.company_name = ""

# Step 1: Upload file and confirm header
with st.expander("📁 Step 1: Upload File", expanded=not st.session_state.header_confirmed):
    if st.session_state.header_confirmed:
        st.success("✅ Step 1 completed")
    file = st.file_uploader("Upload your .csv or .xlsx file", type=["csv", "xlsx"])
    df = None

    if file:
        try:
            df_preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
            st.write("### Preview First 5 Rows:")
            st.dataframe(df_preview.head())

            header_row = st.radio("Which row contains the column headers? ℹ️", df_preview.index[:5], help="Choose the row that contains actual field names like Serial Number, MAC, etc.")
            if st.button("✅ Set Header Row"):
                df = pd.read_csv(file, skiprows=header_row) if file.name.endswith(".csv") else pd.read_excel(file, skiprows=header_row)
                df.columns = df.columns.str.strip()
                st.session_state.df = df
                st.session_state.header_confirmed = True
                st.rerun()
        except Exception as e:
            st.error(f"Error reading file: {e}")

# Spacer before Step 2
st.markdown("\n\n")

# Step 2: Collect device info
step2_expander = st.expander("🔧 Step 2: Add Devices to Convert", expanded=True)
with step2_expander:
    if st.session_state.devices:
        st.success("✅ Step 2 completed")
    st.markdown("\n")
    with st.form("device_form"):
        device_name = st.text_input("Enter device model name ℹ️", help="Found in the Description column of your file")
        load_defaults = st.form_submit_button("🔍 Look Up Device")

        default_type = "ONT"
        default_port = ""
        default_profile_id = ""
        default_password = "no value"
        device_found = False

        if load_defaults:
            st.session_state.device_lookup = {"device_name": device_name, "warning_shown": False}
            if device_name in device_profile_name_map:
                device_found = True
                default_type = device_profile_name_map[device_name]
                template = device_numbers_template_map.get(device_name, "")
                match_port = re.search(r"ONT_PORT=([^|]*)", template)
                match_profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                default_port = match_port.group(1) if match_port else ""
                default_profile_id = match_profile.group(1) if match_profile else ""

        device_types = ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"]
        mapped_type = device_profile_name_map.get(device_name)
        default_index = device_types.index(mapped_type) if mapped_type in device_types else 0
        selected_index = st.selectbox("What type of device is this? ℹ️", device_types, index=default_index if load_defaults else 0, key="device_type_selector", help="Make sure this matches how your system provisions this device")
        device_type = selected_index if isinstance(selected_index, str) else device_types[default_index]

        # If device not found and selected as ONT
        if load_defaults and not device_found and device_type == "ONT":
            st.warning("🚧 This device model name was not found in memory. You can still proceed as ONT by providing required settings.\n\nPlease provide the `ONT_PORT` and `ONT_PROFILE_ID` based on how it's setup in your system.\nIf this device is not in your Camvio inventory, it may fail provisioning. Please contact Camvio Support to add it.")

        if load_defaults and device_name in device_profile_name_map and mapped_type != device_type and mapped_type == "ONT":
            st.warning(f"⚠️ This device is typically identified as `{mapped_type}`. Since you're using `{device_type}`, the system will still treat this as `{mapped_type}` behind the scenes for provisioning. Please verify that your provisioning is properly configured to handle this setup.")

        location = st.selectbox("Where should it be stored? ℹ️", ["WAREHOUSE", "Custom..."], help="Camvio must have this location EXACTLY as shown. Case and spelling matter.")
        if location == "Custom...":
            location = st.text_input("Enter custom location (must match Camvio EXACTLY)")
            st.warning("⚠️ This must exactly match the spelling/case in Camvio or it will fail.")

        custom_ont_port = ""
        custom_profile_id = ""
        if device_type == "ONT":
            st.markdown("#### Customize ONT Settings (required for custom devices)")
            custom_ont_port = st.text_input("ONT_PORT ℹ️", value=default_port, help="The interface this ONT uses to connect (e.g., G1 or x1)")
            custom_profile_id = st.text_input("ONT_PROFILE_ID ℹ️", value=default_profile_id or device_name, help="Provisioning profile used in your system")

        add_device = st.form_submit_button("➕ Add Device")

        if add_device and device_name:
            st.session_state.devices.append({
                "device_name": device_name.strip(),
                "device_type": device_type,
                "location": location.strip(),
                "ONT_PORT": custom_ont_port.strip() if device_type == "ONT" else "",
                "ONT_PROFILE_ID": custom_profile_id.strip() if device_type == "ONT" else "",
                "ONT_MOMENTUM_PASSWORD": "NO VALUE"
            })

    if st.session_state.devices:
        st.markdown("\n")
        st.write("### Devices Selected:")
        for i, d in enumerate(st.session_state.devices):
            cols = st.columns([5, 1])
            with cols[0]:
                st.write(f"🔹 {d['device_name']} → {d['device_type']} @ {d['location']}")
                if d["device_type"] == "ONT":
                    st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE", language="text")
            with cols[1]:
                if st.button("🗑️ Remove", key=f"remove_{i}"):
                    st.session_state.devices.pop(i)
                    st.rerun()

        st.markdown("---")
        if "company_name" not in st.session_state:
            st.session_state.company_name = ""

step3_expander = st.expander("📦 Step 3: Export Setup", expanded=not st.session_state.get("export_complete", False))
if "df" in st.session_state:
    with step3_expander:
        company_input = st.text_input("Enter your company name", value=st.session_state.get("company_name", ""), help="This will be used to name the output file.")
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        st.session_state.company_name = company_input
        export_filename = f"{st.session_state.company_name}_{today_str}.csv" if st.session_state.company_name else "output.csv"

        # Device count summary
        st.subheader("📊 Device Count Summary")

        desc_col = next((col for col in st.session_state.df.columns if 'description' in col.lower()), None)
        if desc_col:
            for d in st.session_state.devices:
                device_model = d["device_name"]
                match_count = st.session_state.df[desc_col].astype(str).str.contains(device_model, case=False, na=False).sum()
                st.markdown(f"- **{device_model}**: {match_count} matching records found in uploaded file")
        else:
            st.warning("Could not locate a Description column to match device names.")

        # Export button and logic
        export_btn = st.button("📤 Export Converted File")
        error_output = io.StringIO()
        error_output.write("device_name,missing_fields,mac,sn,fsan\n")
        valid_rows = 0
        error_rows = 0
        if export_btn:
            output = io.StringIO()
            output.write("device_profile,device_name,device_numbers,inventory_location,inventory_status\n")

            desc_col = next((col for col in st.session_state.df.columns if 'description' in col.lower()), None)
            mac_col = next((col for col in st.session_state.df.columns if 'mac' in col.lower()), None)
            sn_col = next((col for col in st.session_state.df.columns if 'serial' in col.lower() or col.lower() == 'sn'), None)
            fsan_col = next((col for col in st.session_state.df.columns if 'fsan' in col.lower()), None)

            for device in st.session_state.devices:
                device_name = device['device_name']
                profile_type = device_profile_name_map.get(device_name, device['device_type'])
                template = device_numbers_template_map.get(device_name, "MAC=<<MAC>>|SN=<<SN>>|FSAN=<<FSAN>>")

                if profile_type == "ONT":
                    template = f"MAC=<<MAC>>|SN=<<SN>>|ONT_FSAN=<<FSAN>>|ONT_ID=NO VALUE|ONT_NODENAME=NO VALUE|ONT_PORT={device['ONT_PORT']}|ONT_PROFILE_ID={device['ONT_PROFILE_ID']}|ONT_MOMENTUM_PASSWORD={device['ONT_MOMENTUM_PASSWORD']}"
                elif profile_type == "CX_ROUTER":
                    template = f"MAC=<<MAC>>|SN=<<SN>>|ROUTER_FSAN=<<FSAN>>"
                elif profile_type == "CX_MESH":
                    template = f"MAC=<<MAC>>|SN=<<SN>>|MESH_FSAN=<<FSAN>>"
                elif profile_type == "CX_SFP":
                    template = f"MAC=<<MAC>>|SN=<<SN>>|SIP_FSAN=<<FSAN>>"
                elif profile_type == "GAM_COAX_ENDPOINT":
                    template = f"MAC=<<MAC>>|SN=<<SN>>"

                matches = st.session_state.df[st.session_state.df[desc_col].astype(str).str.contains(device_name, case=False, na=False)]

                for _, row in matches.iterrows():
                    mac = str(row.get(mac_col, "")).strip()
                    sn = str(row.get(sn_col, "")).strip()
                    fsan = str(row.get(fsan_col, "")).strip()

                    missing_fields = []
                    if not mac or mac.upper() == "NO VALUE":
                        missing_fields.append("MAC")
                    if not sn or sn.upper() == "NO VALUE":
                        missing_fields.append("Serial Number")
                    if not fsan or fsan.upper() == "NO VALUE":
                        missing_fields.append("FSAN")

                    if missing_fields:
                        error_rows += 1
                        error_output.write(f"{device_name}," + ";".join(missing_fields) + f",{mac},{sn},{fsan}\n")
                        st.error(f"❌ Missing fields for device '{device_name}': {', '.join(missing_fields)}")
                        continue
                    valid_rows += 1
                    numbers = template.replace("<<MAC>>", mac).replace("<<SN>>", sn).replace("<<FSAN>>", fsan)
                    output.write(f"{profile_type},{device_name},{numbers},{device['location']},UNASSIGNED\n")

            st.download_button("⬇️ Download File", data=output.getvalue(), file_name=export_filename, mime="text/csv")
            st.success("✅ Export complete! Please download the file and follow the post-export instructions below.")
            if error_rows > 0:
                st.download_button("⚠️ Download Error Log", data=error_output.getvalue(), file_name="error_log.csv", mime="text/csv")
            st.info("Check the error log for any records that were skipped due to missing MAC, SN, or FSAN values.")
            st.session_state.export_complete = True
            st.rerun()

        st.markdown("""
<details>
<summary>📤 What to do next after export?</summary>

After downloading your converted file:
1. ✅ <strong>Open the CSV and verify</strong> that all device formats look correct.<br>
2. 📦 <strong>Upload the file</strong> to your provisioning or inventory system.<br>
3. 🛠️ If any devices failed export, use the <strong>Error Log</strong> to correct values and re-upload.<br>
4. 💬 <strong>Need help?</strong> Contact Camvio Support if your provisioning setup needs a new device added.

</details>
""", unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("<div style='text-align: right; font-size: 0.75em; color: gray;'>Last updated: 2025-04-03 • Rev: v2.60</div>", unsafe_allow_html=True)

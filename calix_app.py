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

# Step 3: Export setup and file generation
step3_expander = st.expander("📦 Step 3: Export Setup", expanded=True)

if "df" in st.session_state:
    with step3_expander:
        # Ask for company name and format the export file name
        company_input = st.text_input("Enter your company name", value=st.session_state.get("company_name", ""), help="This will be used to name the output file.")
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        st.session_state.company_name = company_input
        export_filename = f"{st.session_state.company_name}_{today_str}.csv" if st.session_state.company_name else "output.csv"

        # Device count summary based on the description column in the uploaded file
        st.subheader("📊 Device Count Summary")

        desc_col = next((col for col in st.session_state.df.columns if 'description' in col.lower()), None)
        if desc_col:
            for d in st.session_state.devices:
                device_model = d["device_name"]
                match_count = st.session_state.df[desc_col].astype(str).str.contains(device_model, case=False, na=False).sum()
                st.markdown(f"- **{device_model}**: {match_count} matching records found in uploaded file")
        else:
            st.warning("Could not locate a Description column to match device names.")

        # Button for Exporting the file
        export_btn = st.button("📤 Export Converted File")
        
        if export_btn:
            # Create in-memory CSV output
            output = io.StringIO()
            output.write("device_profile,device_name,device_numbers,inventory_location,inventory_status\n")

            # Get necessary columns: description, MAC, SN, FSAN
            desc_col = next((col for col in st.session_state.df.columns if 'description' in col.lower()), None)
            mac_col = next((col for col in st.session_state.df.columns if 'mac' in col.lower()), None)
            sn_col = next((col for col in st.session_state.df.columns if 'serial' in col.lower() or col.lower() == 'sn'), None)
            fsan_col = next((col for col in st.session_state.df.columns if 'fsan' in col.lower()), None)

            # Error tracking
            error_output = io.StringIO()
            error_output.write("device_name,missing_fields,mac,sn,fsan\n")
            valid_rows = 0
            error_rows = 0

            # Loop through the devices selected by the user
            for device in st.session_state.devices:
                device_name = device['device_name']
                profile_type = device_profile_name_map.get(device_name, device['device_type'])
                template = device_numbers_template_map.get(device_name, "MAC=<<MAC>>|SN=<<SN>>|FSAN=<<FSAN>>")

                # Template modifications based on device type
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

                # Match rows based on the device name in the description column
                matches = st.session_state.df[st.session_state.df[desc_col].astype(str).str.contains(device_name, case=False, na=False)]

                # Iterate through matched rows
                for _, row in matches.iterrows():
                    mac = str(row.get(mac_col, "")).strip()
                    sn = str(row.get(sn_col, "")).strip()
                    fsan = str(row.get(fsan_col, "")).strip()

                    # Track missing fields and errors
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

            # Downloadable CSV files
            st.download_button("⬇️ Download File", data=output.getvalue(), file_name=export_filename, mime="text/csv")
            st.success("✅ Export complete! Please download the file and follow the post-export instructions below.")

            # Download error log if there were missing fields
            if error_rows > 0:
                st.download_button("⚠️ Download Error Log", data=error_output.getvalue(), file_name="error_log.csv", mime="text/csv")
            st.info("Check the error log for any records that were skipped due to missing MAC, SN, or FSAN values.")

            st.session_state.export_complete = True
            st.rerun()

        # Post-export instructions
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

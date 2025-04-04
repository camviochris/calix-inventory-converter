import streamlit as st
import pandas as pd
import io
import re
import datetime

st.set_page_config(page_title="Calix Inventory Converter", layout="centered")
st.title("📦 Calix Smart Inventory Import Tool")

st.markdown("""
Upload a Calix inventory file (.csv or .xlsx). This tool detects unique device types from the Description column,
prompts you to classify them (ONT, ROUTER, MESH, SFP, ENDPOINT), and converts the inventory into import-ready format.

**No data is stored. Everything runs securely in-memory.**
""")

default_status = 'UNASSIGNED'

# Map device type to profile and template
profile_map = {
    'ONT': 'CALIX_ONT',
    'ROUTER': 'CALIX_ROUTER',
    'MESH': 'CALIX_ROUTER',
    'SFP': 'CALIX_SFP',
    'ENDPOINT': 'CALIX_ENDPOINT'
}

template_map = {
    'ONT': 'MAC=<<MAC>>|SN=<<SN>>|ONT_PORT=1',
    'ROUTER': 'MAC=<<MAC>>|SN=<<SN>>|ONT_PORT=1',
    'MESH': 'MAC=<<MAC>>|SN=<<SN>>|ONT_PORT=1',
    'SFP': 'MAC=<<MAC>>|SN=<<SN>>',
    'ENDPOINT': 'MAC=<<MAC>>|SN=<<SN>>'
}

def find_column(columns, patterns):
    for pat in patterns:
        for col in columns:
            if re.search(pat, col, re.IGNORECASE):
                return col
    return None

uploaded_file = st.file_uploader("Upload your Calix inventory file", type=["csv", "xlsx"])
company_name = st.text_input("Enter your company name (used for output file name)")

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip()

        description_col = find_column(df.columns, [r'description'])
        serial_col = find_column(df.columns, [r'^serial number$', r'^serial$', r'^sn$'])
        mac_col = find_column(df.columns, [r'^mac$', r'^mac address(es)?$'])

        if not all([description_col, serial_col, mac_col]):
            st.error("Missing required columns: Description, Serial Number, or MAC Address")
        else:
            df["Device"] = df[description_col].str.strip()
            unique_devices = df["Device"].dropna().unique()
            st.markdown("### 🔍 Detected Devices:")

            device_selections = {}
            for device in sorted(unique_devices):
                classification = st.selectbox(
                    f"How should '{device}' be classified?",
                    ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"],
                    key=device
                )
                device_selections[device] = classification

            selected_location = st.selectbox("Select location", ["WAREHOUSE", "ITG", "Custom..."])
            if selected_location == "Custom...":
                selected_location = st.text_input("Enter custom location")
                st.warning("⚠️ Custom location must exactly match your system — case and spacing included.")
                confirmed = st.checkbox("✅ I confirm the custom location is correct")
            else:
                confirmed = True

            if company_name and confirmed:
                output_rows = []
                for _, row in df.iterrows():
                    try:
                        device_name = str(row["Device"]).strip()
                        device_type = device_selections.get(device_name)
                        serial = str(row[serial_col]).strip()
                        mac = str(row[mac_col]).strip()

                        profile = profile_map[device_type]
                        template = template_map[device_type]
                        device_numbers = template.replace("<<MAC>>", mac).replace("<<SN>>", serial)

                        output_rows.append({
                            "device_profile": profile,
                            "device_name": device_name,
                            "device_numbers": device_numbers,
                            "location": selected_location,
                            "status": default_status
                        })
                    except Exception as e:
                        st.warning(f"Error processing row: {e}")

                result_df = pd.DataFrame(output_rows)

                st.success("Conversion complete! Preview below:")
                st.dataframe(result_df.head(10))

                today = datetime.date.today().strftime("%Y%m%d")
                safe_company = re.sub(r'[^a-zA-Z0-9_\\-]', '', company_name.lower().replace(' ', '_'))
                file_name = f"{safe_company}_{today}_calix.csv"

                csv_buffer = io.StringIO()
                result_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="📥 Download Converted File",
                    data=csv_buffer.getvalue(),
                    file_name=file_name,
                    mime="text/csv"
                )

    except Exception as e:
        st.error(f"Error reading file: {e}")

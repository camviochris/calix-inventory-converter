import streamlit as st
import pandas as pd
import io
import re
import datetime

st.set_page_config(page_title="Calix Inventory Converter", layout="centered")
st.title("📦 Calix Smart Inventory Import Tool")

st.markdown("""
Upload a Calix inventory file (.csv or .xlsx). This tool lets you confirm your header row,
then detects device types from the Description column, prompts you to classify them,
and converts the inventory into import-ready format.

**No data is stored. Everything runs securely in-memory.**
""")

default_status = 'UNASSIGNED'

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

# Session state
if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False
if "df" not in st.session_state:
    st.session_state.df = None

# Step 1: Header selection
if uploaded_file and not st.session_state.header_confirmed:
    try:
        raw_data = pd.read_csv(uploaded_file, header=None) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file, header=None)
        st.markdown("### Step 1: Select Header Row")
        st.dataframe(raw_data.head(5))
        header_row_index = st.number_input("Which row contains the column headers? (0-indexed)", min_value=0, max_value=4, step=1, value=0)

        if st.button("Confirm Header Row"):
            df = pd.read_csv(uploaded_file, skiprows=header_row_index) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file, skiprows=header_row_index)
            df.columns = df.columns.str.strip()
            st.session_state.df = df
            st.session_state.header_confirmed = True
            st.experimental_rerun()

    except Exception as e:
        st.error(f"Error reading file: {e}")

# Step 2: Classification
if st.session_state.header_confirmed and st.session_state.df is not None:
    df = st.session_state.df
    st.success("Header row confirmed. Continue with classification.")

    description_guess = find_column(df.columns, [r'description', r'product description', r'item description'])
    serial_guess = find_column(df.columns, [r'serial', r'sn'])
    mac_guess = find_column(df.columns, [r'mac'])

    description_col = description_guess or st.selectbox("Select Description column", df.columns.tolist())
    serial_col = serial_guess or st.selectbox("Select Serial Number column", df.columns.tolist())
    mac_col = mac_guess or st.selectbox("Select MAC Address column", df.columns.tolist())
    fsan_col = st.selectbox("Select FSAN column (if any)", ["None"] + df.columns.tolist())

    df["Device"] = df[description_col].astype(str).str.strip()
    unique_devices = df["Device"].dropna().unique()

    st.markdown("### Step 3: Classify Devices")
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
                fsan = str(row[fsan_col]).strip() if fsan_col != "None" else ''

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

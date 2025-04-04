import streamlit as st
import pandas as pd
import re
import io
import datetime

st.set_page_config(page_title="Calix Inventory Import", layout="centered")
st.title("📥 Calix Inventory Import Tool")

# --- Session state init ---
if "step_1_complete" not in st.session_state:
    st.session_state.step_1_complete = False
if "df" not in st.session_state:
    st.session_state.df = None
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None

# --- Step 1: Upload + Header Row Selection ---
with st.expander("🧾 Step 1: Upload File & Select Header", expanded=not st.session_state.step_1_complete):
    uploaded_file = st.file_uploader("Upload your .csv or .xlsx file", type=["csv", "xlsx"])
    st.session_state.uploaded_file = uploaded_file

    if uploaded_file:
        filetype = "csv" if uploaded_file.name.endswith(".csv") else "excel"
        df_preview = pd.read_csv(uploaded_file, header=None) if filetype == "csv" else pd.read_excel(uploaded_file, header=None)
        st.markdown("### Preview first 5 rows:")
        st.dataframe(df_preview.head(5))

        header_idx = st.radio(
            "Which row contains your column headers?",
            options=df_preview.head(5).index.tolist(),
            format_func=lambda x: f"Row {x}",
            horizontal=True
        )

        st.markdown("##### Row Contents (for reference):")
        for i in df_preview.head(5).index:
            st.text(f"Row {i}: {list(df_preview.loc[i].values)}")

        if st.button("✅ Confirm Header Row"):
            df = pd.read_csv(uploaded_file, skiprows=header_idx) if filetype == "csv" else pd.read_excel(uploaded_file, skiprows=header_idx)
            df.columns = df.columns.str.strip()
            st.session_state.df = df
            st.session_state.step_1_complete = True
            st.rerun()

if st.session_state.step_1_complete:
    st.success("✅ Step 1 Complete: Header row was set successfully.")

# --- Step 2: Detect Columns + Classify Devices ---
if st.session_state.step_1_complete and st.session_state.df is not None:
    st.markdown("---")
    st.header("🔍 Step 2: Detect Columns & Classify Devices")

    df = st.session_state.df

    def find_column(columns, patterns):
        for pat in patterns:
            for col in columns:
                if re.search(pat, col, re.IGNORECASE):
                    return col
        return None

    description_col = find_column(df.columns, [r'description', r'product description', r'item description'])
    serial_col = find_column(df.columns, [r'serial number', r'serial', r'sn'])
    mac_col = find_column(df.columns, [r'mac', r'mac address'])
    fsan_col = find_column(df.columns, [r'fsan'])

    if not description_col:
        description_col = st.selectbox("Select Description column", df.columns.tolist())
    if not serial_col:
        serial_col = st.selectbox("Select Serial Number column", df.columns.tolist())
    if not mac_col:
        mac_col = st.selectbox("Select MAC Address column", df.columns.tolist())
    if not fsan_col:
        fsan_col = st.selectbox("Select FSAN column (or choose None)", ["None"] + df.columns.tolist())

    def extract_device_name(desc_column):
        known_starts = {
            'XGS ONT SFP+': 'SFP-XGS',
            'GigaSpire u4xg, GS2128XG': 'GS2128XG',
            'GigaSpire BLAST u10xe GS4237': 'GS4237',
            'GigaSpire BLAST u6txg, GS5229XG': 'GS5229XG',
            'GigaSpire BLAST u6t, GS5229E': 'GS5229E',
            'GigaPro GPR2032H': 'GPR2032H',
            'GigaPro GPR8802x': 'GPR8802X',
            'GigaSpire u4hm, GM1028H': 'GM1028H',
            'GPON ONT SFP Module': 'SFP-GPON',
            '812G-1 GigaHub': '812G',
            'GS2028E': 'GS2028E',
            'GP1100G GigaPoint': 'GP1100G',
            'GigaSpire u6.3': 'GS4229E',
            'G1001-C': 'G1001-C',
            'GigaSpire 7u10t, 10GE Tri Gateway, GS5239E': 'GS5239E'
        }
        for pattern, device in known_starts.items():
            if desc_column.startswith(pattern):
                return device

        # Fallback
        for delim in [',', ';', ' ']:
            if delim in desc_column:
                return desc_column.split(delim)[0].strip()
        return desc_column.strip()

    df["Device Name"] = df[description_col].astype(str).apply(extract_device_name)
    unique_devices = sorted(df["Device Name"].dropna().unique())

    st.markdown("### 📦 Classify Detected Devices")
    device_config = {}
    for device in unique_devices:
        cols = st.columns([3, 2])
        with cols[0]:
            classification = st.selectbox(f"Device '{device}' type:", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"], key=f"type_{device}")
        with cols[1]:
            location = st.selectbox(f"Location for '{device}':", ["WAREHOUSE", "ITG", "Custom..."], key=f"loc_{device}")
            if location == "Custom...":
                location = st.text_input(f"Enter custom location for '{device}'", key=f"custom_loc_{device}")
        device_config[device] = {"type": classification, "location": location}

    st.session_state.device_config = device_config
    st.session_state.description_col = description_col
    st.session_state.serial_col = serial_col
    st.session_state.mac_col = mac_col
    st.session_state.fsan_col = fsan_col if fsan_col != "None" else None

# --- Step 3: Output + Download ---
if "device_config" in st.session_state and st.session_state.device_config:
    st.markdown("---")
    st.header("📤 Step 3: Generate Output File")

    # Profile + Template Maps (from your script)
    from mappings import device_profile_name_map, device_numbers_template_map  # Assume these are defined in mappings.py or inline

    company_name = st.text_input("Enter your company name (used for output file name):")

    if company_name:
        output_rows = []
        for _, row in df.iterrows():
            device_name = str(row["Device Name"]).strip()
            serial = str(row[st.session_state.serial_col]).strip()
            mac = str(row[st.session_state.mac_col]).strip()
            fsan = str(row[st.session_state.fsan_col]).strip() if st.session_state.fsan_col else ""

            template = device_numbers_template_map.get(device_name)
            profile = device_profile_name_map.get(device_name)

            if not template or not profile:
                st.warning(f"⚠️ Device '{device_name}' is not in the template map. Skipping.")
                continue

            config = st.session_state.device_config.get(device_name, {})
            location = config.get("location", "WAREHOUSE")

            device_numbers = (
                template.replace("<<MAC>>", mac)
                        .replace("<<SN>>", serial)
                        .replace("<<FSAN>>", fsan)
            )

            output_rows.append({
                "device_profile": profile,
                "device_name": device_name,
                "device_numbers": device_numbers,
                "location": location,
                "status": "UNASSIGNED"
            })

        result_df = pd.DataFrame(output_rows)

        st.success("🎉 Conversion complete! Preview below:")
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

# --- Revision Footer ---
st.markdown("---")
st.markdown(
    "<div style='text-align: right; font-size: 0.75em; color: gray;'>"
    "Last updated: 2025-04-03 &nbsp; • &nbsp; Rev: v1.50"
    "</div>",
    unsafe_allow_html=True
)

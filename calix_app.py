import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Calix Inventory Import", layout="centered")
st.title("📥 Calix Inventory Import Tool")

# Session state initialization
if "step_1_complete" not in st.session_state:
    st.session_state.step_1_complete = False
if "df" not in st.session_state:
    st.session_state.df = None
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None

# Step 1: Upload and Header Row Selection
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

# ✅ Step 1 Success Indicator
if st.session_state.step_1_complete:
    st.success("✅ Step 1 Complete: Header row was set successfully.")

# Step 2: Auto-Detect Columns & Classify Devices
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

    # Fallbacks if not auto-detected
    if not description_col:
        description_col = st.selectbox("Select Description column", df.columns.tolist())
    if not serial_col:
        serial_col = st.selectbox("Select Serial Number column", df.columns.tolist())
    if not mac_col:
        mac_col = st.selectbox("Select MAC Address column", df.columns.tolist())
    if not fsan_col:
        fsan_col = st.selectbox("Select FSAN column (or choose None)", ["None"] + df.columns.tolist())

    # Extract device name from Description
    def extract_device_name(description):
        known_prefixes = ['GigaSpire', 'GigaPro', 'GPON', 'GS', 'GM', 'GP', 'XGS', '812G', '803G', 'G1001', 'SFP']
        for prefix in known_prefixes:
            if prefix in description:
                return next((word for word in description.split() if prefix in word), description[:15])
        return re.split(r'[ ,;]', description.strip())[0]

    df["Device Name"] = df[description_col].astype(str).apply(extract_device_name)
    unique_devices = sorted(df["Device Name"].dropna().unique())

    # Let user classify and assign location for each unique device
    st.markdown("### 📦 Classify Detected Devices")
    device_config = {}
    for device in unique_devices:
        cols = st.columns([3, 2])
        with cols[0]:
            classification = st.selectbox(
                f"Device '{device}' type:",
                ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"],
                key=f"type_{device}"
            )
        with cols[1]:
            location = st.selectbox(
                f"Location for '{device}':",
                ["WAREHOUSE", "ITG", "Custom..."],
                key=f"loc_{device}"
            )
            if location == "Custom...":
                location = st.text_input(f"Enter custom location for '{device}'", key=f"custom_loc_{device}")
        device_config[device] = {"type": classification, "location": location}

    # Save for next step
    st.session_state.device_config = device_config
    st.session_state.description_col = description_col
    st.session_state.serial_col = serial_col
    st.session_state.mac_col = mac_col
    st.session_state.fsan_col = fsan_col if fsan_col != "None" else None

import streamlit as st
import pandas as pd
import re
import io
import datetime
from mappings import device_profile_name_map, device_numbers_template_map

st.set_page_config(page_title="Calix Inventory Import", layout="centered")
st.title("📥 Calix Inventory Import Tool")

# Session state
if "devices" not in st.session_state:
    st.session_state.devices = []

# Step 1: Upload file and confirm header
st.header("📁 Step 1: Upload File")
file = st.file_uploader("Upload your .csv or .xlsx file", type=["csv", "xlsx"])
df = None

if file:
    try:
        df_preview = pd.read_csv(file, header=None) if file.name.endswith(".csv") else pd.read_excel(file, header=None)
        st.write("### Preview First 5 Rows:")
        st.dataframe(df_preview.head())

        header_row = st.radio("Which row contains the column headers?", df_preview.index[:5])
        if st.button("✅ Set Header Row"):
            df = pd.read_csv(file, skiprows=header_row) if file.name.endswith(".csv") else pd.read_excel(file, skiprows=header_row)
            df.columns = df.columns.str.strip()
            st.session_state.df = df
            st.success("Header row set. Continue below.")
    except Exception as e:
        st.error(f"Error reading file: {e}")

# Step 2: Collect device info
if "df" in st.session_state:
    st.markdown("---")
    st.header("🔧 Step 2: Add Devices to Convert")
    with st.form("device_form"):
        device_name = st.text_input("Enter device model name (as found in Description column)")
        default_type = "ONT"
        default_port = ""
        default_profile_id = ""
        default_password = "no value"

        if device_name in device_profile_name_map:
            default_type = device_profile_name_map[device_name]
            template = device_numbers_template_map.get(device_name, "")
            match_port = re.search(r"ONT_PORT=([^|]*)", template)
            match_profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
            match_pass = re.search(r"ONT_MOMENTUM_PASSWORD=([^|]*)", template)
            default_port = match_port.group(1) if match_port else ""
            default_profile_id = match_profile.group(1) if match_profile else ""
            default_password = match_pass.group(1) if match_pass else "no value"

        device_type = st.selectbox("What type of device is this?", ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"], index=["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"].index(default_type))
        location = st.selectbox("Where should it be stored?", ["WAREHOUSE", "Custom..."])
        if location == "Custom...":
            location = st.text_input("Enter custom location (must match Camvio EXACTLY)")
            st.warning("⚠️ This must exactly match the spelling/case in Camvio or it will fail.")

        # Show default values for ONT customization
        custom_ont_port = ""
        custom_profile_id = ""
        custom_password = ""
        if device_type == "ONT":
            st.markdown("#### Customize ONT Settings (optional)")
            custom_ont_port = st.text_input("ONT_PORT", value=default_port)
            custom_profile_id = st.text_input("ONT_PROFILE_ID", value=default_profile_id or device_name)
            custom_password = st.text_input("ONT_MOMENTUM_PASSWORD", value=default_password)

        add_device = st.form_submit_button("➕ Add Device")

        if add_device and device_name:
            st.session_state.devices.append({
                "device_name": device_name.strip(),
                "device_type": device_type,
                "location": location.strip(),
                "ONT_PORT": custom_ont_port.strip(),
                "ONT_PROFILE_ID": custom_profile_id.strip(),
                "ONT_MOMENTUM_PASSWORD": custom_password.strip()
            })

    if st.session_state.devices:
        st.write("### Devices Selected:")
        for d in st.session_state.devices:
            st.write(f"🔹 {d['device_name']} → {d['device_type']} @ {d['location']}")
            if d["device_type"] == "ONT":
                st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: {d['ONT_MOMENTUM_PASSWORD']}", language="text")

# Step 3: Process and Output
if st.session_state.devices:
    st.markdown("---")
    st.header("📤 Step 3: Generate Output")
    company = st.text_input("Company name (used in output filename)")

    if company:
        matched_rows = []
        df = st.session_state.df
        df = df.fillna("")
        columns = df.columns.str.lower()

        def find_column(possibles):
            for col in df.columns:
                if any(re.search(p, col, re.IGNORECASE) for p in possibles):
                    return col
            return None

        desc_col = find_column(["description", "product description", "item description"])
        serial_col = find_column(["serial", "sn"])
        mac_col = find_column(["mac"])
        fsan_col = find_column(["fsan"])

        for dev in st.session_state.devices:
            name = dev["device_name"]
            rows = df[df[desc_col].str.contains(name, case=False, na=False)]
            profile = device_profile_name_map.get(name)
            template = device_numbers_template_map.get(name)

            if not profile or not template:
                st.warning(f"⚠️ Device '{name}' not in template/profile map. Skipping.")
                continue

            # Customize ONT template if needed
            if dev["device_type"] == "ONT":
                if "<<ONT_PORT>>" in template or "ONT_PORT=" in template:
                    template = re.sub(r"ONT_PORT=[^|]*", f"ONT_PORT={dev['ONT_PORT']}", template)
                if "<<ONT_PROFILE_ID>>" in template or "ONT_PROFILE_ID=" in template:
                    template = re.sub(r"ONT_PROFILE_ID=[^|]*", f"ONT_PROFILE_ID={dev['ONT_PROFILE_ID']}", template)
                if "<<ONT_MOMENTUM_PASSWORD>>" in template or "ONT_MOMENTUM_PASSWORD=" in template:
                    template = re.sub(r"ONT_MOMENTUM_PASSWORD=[^|]*", f"ONT_MOMENTUM_PASSWORD={dev['ONT_MOMENTUM_PASSWORD']}", template)

            for _, row in rows.iterrows():
                mac = str(row.get(mac_col, "")).strip()
                sn = str(row.get(serial_col, "")).strip()
                fsan = str(row.get(fsan_col, "")).strip() if fsan_col else ""
                device_numbers = template.replace("<<MAC>>", mac).replace("<<SN>>", sn).replace("<<FSAN>>", fsan)
                matched_rows.append({
                    "device_profile": profile,
                    "device_name": name,
                    "device_numbers": device_numbers,
                    "location": dev["location"],
                    "status": "UNASSIGNED"
                })

        result_df = pd.DataFrame(matched_rows)
        if not result_df.empty:
            st.success("🎉 Conversion complete!")
            st.dataframe(result_df.head(10))
            csv_buffer = io.StringIO()
            result_df.to_csv(csv_buffer, index=False)
            today = datetime.date.today().strftime("%Y%m%d")
            safe_company = re.sub(r'[^a-zA-Z0-9_\-]', '', company.lower().replace(' ', '_'))
            file_name = f"{safe_company}_{today}_calix.csv"
            st.download_button("📥 Download CSV", data=csv_buffer.getvalue(), file_name=file_name, mime="text/csv")
        else:
            st.info("No matching records found in Description column.")

# Footer
st.markdown("---")
st.markdown("<div style='text-align: right; font-size: 0.75em; color: gray;'>Last updated: 2025-04-03 • Rev: v2.11</div>", unsafe_allow_html=True)

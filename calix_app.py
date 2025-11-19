from datetime import datetime
import io
import re

import pandas as pd
import streamlit as st

from mappings import device_profile_name_map, device_numbers_template_map


# --- Helpers -----------------------------------------------------------------


def auto_detect_header_row(df: pd.DataFrame) -> int:
    """
    Try to find the row that contains header names like 'Item Description' / 'Description'
    and 'FSAN'. Look at the first 10 rows. Fallback to row 0.
    """
    max_scan_rows = min(10, len(df))

    # Pass 1 – look for a row that has BOTH description & FSAN-ish cells.
    for idx in range(max_scan_rows):
        row = df.iloc[idx]
        cells = [str(x).strip().lower() for x in row]
        has_desc = any("description" in c for c in cells)
        has_fsan = any("fsan" in c for c in cells)
        if has_desc and has_fsan:
            return idx

    # Pass 2 – any row with a description-ish header.
    for idx in range(max_scan_rows):
        row = df.iloc[idx]
        cells = [str(x).strip().lower() for x in row]
        if any("description" in c for c in cells):
            return idx

    # Fallback
    return 0


def device_profile_to_type(profile: str) -> str:
    """
    Map profile name from mappings.py to the friendly device_type used in the UI.
    """
    if profile == "ONT":
        return "ONT"
    if profile == "CX_ROUTER":
        return "ROUTER"
    if profile == "CX_MESH":
        return "MESH"
    if profile == "CX_SFP":
        return "SFP"
    # Fallback for anything else (GAM_COAX_ENDPOINT, etc.)
    return "ENDPOINT"


def build_devices_from_descriptions(df: pd.DataFrame, desc_col: str):
    """
    Scan the description column, find all known models from mappings.py, and
    return a list of device dicts with counts and default ONT fields.

    Uses regex "word-ish" boundaries so 'GM1028' does NOT match 'GM1028H'.
    """
    devices = []
    desc_series = df[desc_col].astype(str)

    for device_name, profile in device_profile_name_map.items():
        # Skip ALT entries – they're used only when building device_numbers
        if str(device_name).endswith("_ALT"):
            continue

        pattern = str(device_name)

        # Word-ish boundary: no letter/number immediately before or after
        pattern_regex = rf"(?<![A-Za-z0-9]){re.escape(pattern)}(?![A-Za-z0-9])"

        mask = desc_series.str.contains(
            pattern_regex, case=False, na=False, regex=True
        )
        count = int(mask.sum())
        if count == 0:
            continue

        # Try to pull defaults for ONT_PORT / ONT_PROFILE_ID from the template
        template = (
            device_numbers_template_map.get(str(device_name), "")
            or device_numbers_template_map.get(str(device_name).upper(), "")
        )

        ont_port = ""
        ont_profile_id = ""

        if "ONT_PORT=" in template:
            m = re.search(r"ONT_PORT=([^|]*)", template)
            if m:
                ont_port = m.group(1)

        if "ONT_PROFILE_ID=" in template:
            m = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
            if m:
                ont_profile_id = m.group(1)

        devices.append(
            {
                "model_name": pattern,  # used to match Item Description
                "device_name": device_name,
                "device_type": device_profile_to_type(profile),
                "location": "WAREHOUSE",
                "ONT_PORT": ont_port,
                "ONT_PROFILE_ID": ont_profile_id,
                "exclude_mac_sn": False,
                "count": count,
            }
        )

    return devices


def make_model_regex(model: str) -> str:
    """
    Build the same 'word-ish boundary' regex used in build_devices_from_descriptions,
    so counts and export rows line up and we avoid GM1028 vs GM1028H double matches.
    """
    return rf"(?<![A-Za-z0-9]){re.escape(str(model))}(?![A-Za-z0-9])"


# --- Session state -----------------------------------------------------------

if "devices" not in st.session_state:
    st.session_state.devices = []

if "header_confirmed" not in st.session_state:
    st.session_state.header_confirmed = False

if "df" not in st.session_state:
    st.session_state.df = None

if "auto_devices_initialized" not in st.session_state:
    st.session_state.auto_devices_initialized = False

if "company_name" not in st.session_state:
    st.session_state.company_name = ""

if "file_name" not in st.session_state:
    st.session_state.file_name = ""


# --- Page setup --------------------------------------------------------------

st.set_page_config(page_title="Calix Inventory Converter", layout="wide")
st.title("📅 Calix Inventory Converter")

with st.expander("❓ How to Use This Tool", expanded=False):
    st.markdown(
        """
This tool converts ISP inventory exports into a Calix-ready import file.

**Workflow:**
1. Upload a `.csv` or `.xlsx` file.
2. The app automatically detects the header row (Item Description / FSAN).
3. It scans *Item Description* using `mappings.py` to find all known devices.
4. It shows each **unique device** found, the **device type**, and **record count**.
5. For ONTs, you can tweak **ONT_PORT** and **ONT_PROFILE_ID** per run.
6. Export a Calix-ready CSV and see total exported record count.
        """
    )

# --- Reset button ------------------------------------------------------------

if st.button("🔄 Reset All"):
    st.session_state.devices = []
    st.session_state.header_confirmed = False
    st.session_state.df = None
    st.session_state.auto_devices_initialized = False
    st.session_state.file_name = ""
    st.rerun()

# Optional company name just for file naming
st.text_input(
    "Company name (optional – only used in export file name)",
    key="company_name",
)


# --- Step 1: Upload file & auto-detect header --------------------------------

with st.expander(
    "📁 Step 1: Upload Inventory File",
    expanded=not st.session_state.header_confirmed,
):
    file = st.file_uploader("Upload your inventory file", type=["csv", "xlsx"])

    if file and not st.session_state.header_confirmed:
        # Read with no header so we can find it ourselves
        if file.name.lower().endswith(".csv"):
            raw_df = pd.read_csv(file, header=None)
        else:
            raw_df = pd.read_excel(file, header=None)

        st.write("🔎 **Preview – first 5 rows (raw)**")
        st.dataframe(raw_df.head())

        header_row_idx = auto_detect_header_row(raw_df)
        header_row = raw_df.iloc[header_row_idx].astype(str).str.strip()

        df = raw_df.iloc[header_row_idx + 1 :].copy()
        df.columns = header_row
        df.columns = df.columns.str.strip()

        st.session_state.df = df
        st.session_state.header_confirmed = True
        st.session_state.auto_devices_initialized = False
        st.session_state.file_name = file.name

        st.success(f"✅ Header row auto-detected at raw row index {header_row_idx}.")
        st.write("🧾 **Detected columns:**")
        st.write(list(df.columns))

        st.rerun()


# --- Step 2: Auto-detect devices from Item Description -----------------------

if st.session_state.header_confirmed and st.session_state.df is not None:
    df = st.session_state.df

    # Try to locate commonly-named columns
    desc_col = next(
        (col for col in df.columns if "description" in str(col).lower()),
        None,
    )
    mac_col = next(
        (col for col in df.columns if "mac" in str(col).lower()),
        None,
    )
    sn_col = next(
        (
            col
            for col in df.columns
            if "serial" in str(col).lower() or str(col).lower() == "sn"
        ),
        None,
    )
    fsan_col = next(
        (col for col in df.columns if "fsan" in str(col).lower()),
        None,
    )

    if not desc_col:
        st.error(
            "❌ Could not detect an Item Description column. "
            "Make sure one of your headers contains the word 'Description'."
        )
        st.stop()

    if not fsan_col:
        st.warning(
            "⚠️ Could not detect an FSAN column automatically. "
            "If your templates require FSAN, those rows may not export correctly."
        )

    # Build devices once per upload
    if not st.session_state.auto_devices_initialized:
        st.session_state.devices = build_devices_from_descriptions(df, desc_col)
        st.session_state.auto_devices_initialized = True

    # --- Summary at the top so you can compare counts ------------------------
    total_rows = len(df)
    sum_device_counts = sum(d.get("count", 0) for d in st.session_state.devices)

    st.markdown("### 📊 File & Record Summary")
    st.markdown(
        f"- **File name:** `{st.session_state.file_name or 'N/A'}`  \n"
        f"- **Total rows detected (excluding header):** **{total_rows}**  \n"
        f"- **Sum of device record counts (from Item Description):** **{sum_device_counts}**"
    )
    st.caption(
        "If these don't match, either some rows don't match any known device, "
        "or descriptions contain patterns that don't align with `mappings.py`."
    )

    # --- Devices list --------------------------------------------------------
    st.markdown("### 🔍 Step 2: Devices found from Item Description")

    if not st.session_state.devices:
        st.info(
            "No known devices from `mappings.py` were found in the Item Description column."
        )
    else:
        # iterate over a copy of the list so removals don't mess up the loop
        for idx, device in enumerate(list(st.session_state.devices)):
            st.markdown(
                f"**{device['device_name']}** "
                f"({device['device_type']}) – **{device['count']}** matching records"
            )

            # For ONTs allow editing ONT_PORT and ONT_PROFILE_ID per device
            if device["device_type"] == "ONT":
                c1, c2 = st.columns(2)
                with c1:
                    new_port = st.text_input(
                        f"ONT_PORT for {device['device_name']}",
                        value=device.get("ONT_PORT", ""),
                        key=f"ont_port_{idx}",
                    )
                with c2:
                    new_profile = st.text_input(
                        f"ONT_PROFILE_ID for {device['device_name']}",
                        value=device.get("ONT_PROFILE_ID", ""),
                        key=f"ont_profile_{idx}",
                    )

                st.session_state.devices[idx]["ONT_PORT"] = new_port
                st.session_state.devices[idx]["ONT_PROFILE_ID"] = new_profile

            # Optional remove
            if st.button("🗑️ Remove", key=f"remove_{idx}"):
                st.session_state.devices.pop(idx)
                st.rerun()


# --- Step 3: Export ----------------------------------------------------------

if st.session_state.header_confirmed and st.session_state.df is not None:
    df = st.session_state.df

    with st.expander("📦 Step 3: Export Calix file", expanded=True):
        if not st.session_state.devices:
            st.info("No devices selected/found to export.")
            st.stop()

        # Re-locate key columns (just to be safe)
        desc_col = next(
            (col for col in df.columns if "description" in str(col).lower()),
            None,
        )
        mac_col = next(
            (col for col in df.columns if "mac" in str(col).lower()),
            None,
        )
        sn_col = next(
            (
                col
                for col in df.columns
                if "serial" in str(col).lower() or str(col).lower() == "sn"
            ),
            None,
        )
        fsan_col = next(
            (col for col in df.columns if "fsan" in str(col).lower()),
            None,
        )

        if not desc_col:
            st.error("❌ Item Description column not found; cannot export.")
            st.stop()

        # Map device profile → FSAN label in the template
        fsan_label_map = {
            "ONT": "ONT_FSAN",
            "CX_ROUTER": "ROUTER_FSAN",
            "CX_MESH": "MESH_FSAN",
            "CX_SFP": "SIP_FSAN",
            "GAM_COAX_ENDPOINT": "GAM_FSAN",
        }

        # Build filename
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = (
            st.session_state.company_name.strip().replace(" ", "_")
            if st.session_state.company_name
            else "inventory"
        )
        export_name = f"{base_name}_{ts}.csv"

        output = io.StringIO()
        output.write(
            "device_profile,device_name,device_numbers,inventory_location,inventory_status\n"
        )

        total_records = 0

        for device in st.session_state.devices:
            name = device["device_name"]
            model = device["model_name"]
            dtype = device["device_type"]

            # Profile from mappings; fall back if somehow missing
            profile = (
                device_profile_name_map.get(str(name))
                or device_profile_name_map.get(str(name).upper())
                or f"CX_{dtype}"
            )

            fsan_label = fsan_label_map.get(profile, "FSAN")

            template_key = f"{name}_ALT" if device.get("exclude_mac_sn") else name
            template = (
                device_numbers_template_map.get(str(template_key))
                or device_numbers_template_map.get(str(template_key).upper(), "")
            )

            pattern_regex = make_model_regex(model)

            matches = df[
                df[desc_col]
                .astype(str)
                .str.contains(pattern_regex, case=False, na=False, regex=True)
            ]

            for _, row in matches.iterrows():
                mac = str(row[mac_col]).strip() if mac_col in df.columns else ""
                sn = str(row[sn_col]).strip() if sn_col in df.columns else ""
                fsan = str(row[fsan_col]).strip() if fsan_col in df.columns else ""

                # If we truly have nothing, skip
                if not any([mac, sn, fsan]):
                    continue

                if template:
                    device_numbers = (
                        template.replace("<<MAC>>", mac)
                        .replace("<<SN>>", sn)
                        .replace("<<FSAN>>", fsan)
                        .replace("<<ONT_PORT>>", device.get("ONT_PORT", ""))
                        .replace("<<ONT_PROFILE_ID>>", device.get("ONT_PROFILE_ID", ""))
                    )
                else:
                    # Very generic fallback
                    parts = []
                    if mac:
                        parts.append(f"MAC={mac}")
                    if sn:
                        parts.append(f"SN={sn}")
                    if fsan:
                        parts.append(f"{fsan_label}={fsan}")
                    device_numbers = "|".join(parts)

                output.write(
                    f"{profile},{name},{device_numbers},{device['location']},UNASSIGNED\n"
                )
                total_records += 1

        st.download_button(
            "⬇️ Export & Download File",
            data=output.getvalue(),
            file_name=export_name,
            mime="text/csv",
        )
        st.success("✅ File is ready for download.")
        st.info(f"ℹ️ Exported **{total_records}** records (excluding header).")

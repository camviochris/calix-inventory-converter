import streamlit as st
import pandas as pd

st.set_page_config(page_title="Calix Inventory - Step 1", layout="centered")
st.title("📥 Calix Inventory Import")

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

# ✅ Step 1 Success Banner
if st.session_state.step_1_complete:
    st.success("✅ Step 1 Complete: Header row was set successfully.")

# Step 2 Placeholder
if st.session_state.step_1_complete and st.session_state.df is not None:
    st.markdown("---")
    st.header("Step 2: Coming Next")
    st.info("This is where we’ll auto-detect and classify your device descriptions in the next step.")

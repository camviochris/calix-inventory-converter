import streamlit as st
import pandas as pd

st.set_page_config(page_title="Calix Inventory - Step 1", layout="centered")
st.title("📥 Step 1: Upload Calix Inventory File")

uploaded_file = st.file_uploader("Upload your .csv or .xlsx file", type=["csv", "xlsx"])

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

    with st.expander("🔍 Show row contents"):
        for i in df_preview.head(5).index:
            st.text(f"Row {i}: {list(df_preview.loc[i].values)}")

    if st.button("✅ Confirm Header Row"):
        df = pd.read_csv(uploaded_file, skiprows=header_idx) if filetype == "csv" else pd.read_excel(uploaded_file, skiprows=header_idx)
        df.columns = df.columns.str.strip()
        st.success("Header row set. Here’s a preview:")
        st.dataframe(df.head())

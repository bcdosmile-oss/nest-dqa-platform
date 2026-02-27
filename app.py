import streamlit as st
import pandas as pd

st.title("NEST360 DQA System")

uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])

if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.write("Data Preview")
    st.dataframe(df.head())

    st.success("App is working ✅")

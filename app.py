import streamlit as st
import pandas as pd

st.set_page_config(page_title="NEST360 DQA System", layout="wide")

# ------------------------
# PASSWORD PROTECTION
# ------------------------

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("🔐 NEST360 Internal DQA System")

    password = st.text_input("Enter Password", type="password")

    if st.button("Login"):
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect Password")

    st.stop()

check_password()
with st.sidebar:
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()
# ------------------------
# MAIN APP
# ------------------------

st.title("🏥 NEST360 Health Data Reporting & DQA")

uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])

if uploaded_file is not None:

    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.subheader("Data Preview")
    st.dataframe(df.head())

    missing = df.isnull().sum()
    duplicates = df.duplicated().sum()

    total_records = len(df)
    total_errors = missing.sum() + duplicates

    dqa_score = max(0, 100 - ((total_errors / (total_records + 1)) * 100))

    if dqa_score >= 95:
        status = "🟢 GREEN"
    elif dqa_score >= 80:
        status = "🟡 YELLOW"
    else:
        status = "🔴 RED"

    col1, col2 = st.columns(2)
    col1.metric("DQA Score", f"{dqa_score:.2f}%")
    col2.metric("Status", status)

    st.subheader("Missing Values")
    st.dataframe(missing)

    st.write("Duplicate Records:", duplicates)

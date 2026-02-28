import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io

st.set_page_config(page_title="NEST360 Internal DQA", layout="wide")

# ------------------------
# PASSWORD PROTECTION
# ------------------------
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("🔐 NEST360 Internal DQA System")
    pw = st.text_input("Enter access password", type="password")

    if st.button("Login"):
        if pw == st.secrets.get("APP_PASSWORD", ""):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

check_password()

with st.sidebar:
    st.header("Controls")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

st.title("🏥 NEST360 Health Data Reporting & DQA")

uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
if uploaded_file is None:
    st.info("Upload a CSV/Excel export from REDCap to begin.")
    st.stop()

# ------------------------
# LOAD DATA
# ------------------------
if uploaded_file.name.lower().endswith(".csv"):
    df = pd.read_csv(uploaded_file)
else:
    df = pd.read_excel(uploaded_file)

original_cols = list(df.columns)

st.subheader("Data Preview")
st.dataframe(df.head(20), use_container_width=True)

# ------------------------
# COLUMN MAPPING (User selects)
# ------------------------
st.subheader("1) Column mapping (select correctly)")

col1, col2, col3 = st.columns(3)

with col1:
    facility_col = st.selectbox(
        "Facility column",
        options=original_cols,
        index=original_cols.index("Facility Name") if "Facility Name" in original_cols else 0
    )

with col2:
    bw_col = st.selectbox(
        "Birth weight (grams) column",
        options=original_cols,
        index=original_cols.index("Birth weight (grams):") if "Birth weight (grams):" in original_cols else 0
    )

with col3:
    ga_col = st.selectbox(
        "Gestational age (weeks) column",
        options=original_cols,
        index=original_cols.index("Weeks:") if "Weeks:" in original_cols else 0
    )

col4, col5, col6 = st.columns(3)

with col4:
    cpap_col = st.selectbox(
        "CPAP administered column",
        options=["(None)"] + original_cols,
        index=(["(None)"] + original_cols).index("CPAP Administered:") if "CPAP Administered:" in original_cols else 0
    )

with col5:
    kmc_col = st.selectbox(
        "KMC administered column",
        options=["(None)"] + original_cols,
        index=(["(None)"] + original_cols).index("KMC Administered:") if "KMC Administered:" in original_cols else 0
    )

with col6:
    outcome_col = st.selectbox(
        "Outcome/Mortality column (preferred: Newborn status at discharge)",
        options=["(None)"] + original_cols,
        index=(["(None)"] + original_cols).index("Newborn status at discharge:") if "Newborn status at discharge:" in original_cols else 0
    )

# ------------------------
# PREP WORK (numeric conversions + categories)
# ------------------------
work = df.copy()
# ------------------------
# FILTER: Final + Prospective ONLY (Robust Version)
# ------------------------
final_col = "Are you entering a BASELINE or FINAL dataset record?"
rp_col = "Are you entering a RETROSPECTIVE or PROSPECTIVE record?"

if final_col in work.columns and rp_col in work.columns:

    before = len(work)

    # Convert to string safely
    final_series = work[final_col].astype(str).str.strip().str.lower()
    rp_series = work[rp_col].astype(str).str.strip().str.lower()

    # Keep records where:
    # - Final column contains "final" OR equals coded value "2"
    # - Prospective column contains "prospective" OR equals coded value "2"

    work = work[
        (
            final_series.str.contains("final", na=False) |
            final_series.isin(["2", "final"])
        )
        &
        (
            rp_series.str.contains("prospective", na=False) |
            rp_series.isin(["2", "prospective"])
        )
    ].copy()

    removed = before - len(work)

    st.success(f"Filtered to Final + Prospective only: {len(work):,} records (removed {removed:,}).")

    if len(work) == 0:
        st.error("After filtering to Final + Prospective, no records remain. Check your dataset export.")
        st.stop()

else:
    st.warning("Final/Prospective columns not found in this file. No baseline filter applied.")
work[facility_col] = work[facility_col].astype(str).str.strip()

bw = pd.to_numeric(work[bw_col], errors="coerce")
ga = pd.to_numeric(work[ga_col], errors="coerce")

def bw_category(x):
    if pd.isna(x): return "Missing"
    if x < 1000: return "<1000g"
    if 1000 <= x <= 1499: return "1000–1499g"
    if 1500 <= x <= 2499: return "1500–2499g"
    return "≥2500g"

def ga_category(x):
    if pd.isna(x): return "Missing"
    if x < 28: return "<28 weeks"
    if 28 <= x < 32: return "28–<32 weeks"
    if 32 <= x < 37: return "32–<37 weeks"
    return "≥37 weeks"

work["bw_cat"] = bw.map(bw_category)
work["ga_cat"] = ga.map(ga_category)

# ------------------------
# ANALYSIS MODE (All vs Single facility)
# ------------------------
st.subheader("2) Analysis mode")

all_facilities = sorted([f for f in work[facility_col].dropna().unique() if f.lower() != "nan"])

mode = st.radio(
    "Choose analysis scope",
    ["All facilities (aggregate)", "Single facility (facility report)"],
    horizontal=True
)

if mode == "Single facility (facility report)":
    selected_facility = st.selectbox("Select facility", options=all_facilities)
    data = work[work[facility_col] == selected_facility].copy()
    st.info(f"Showing results for: **{selected_facility}** (n={len(data):,})")
else:
    data = work.copy()
    st.info(f"Showing results for: **All facilities (aggregate)** (n={len(data):,})")

# ------------------------
# DQA SUMMARY (based on current scope)
# ------------------------
st.subheader("3) Data Quality Assurance (DQA) summary")

total_rows = len(data)
duplicates = int(data.duplicated().sum())

key_cols = [facility_col, bw_col, ga_col]
if cpap_col != "(None)":
    key_cols.append(cpap_col)
if kmc_col != "(None)":
    key_cols.append(kmc_col)
if outcome_col != "(None)":
    key_cols.append(outcome_col)

missing_key = data[key_cols].isna().sum().sort_values(ascending=False)
missing_key_total = int(missing_key.sum())

bw_scoped = pd.to_numeric(data[bw_col], errors="coerce")
ga_scoped = pd.to_numeric(data[ga_col], errors="coerce")

bw_out_of_range = int(((bw_scoped < 300) | (bw_scoped > 5500)).sum())
ga_out_of_range = int(((ga_scoped < 20) | (ga_scoped > 44)).sum())

error_points = missing_key_total + duplicates + bw_out_of_range + ga_out_of_range
dqa_score = max(0.0, 100.0 - (error_points / (total_rows + 1)) * 100.0)

if dqa_score >= 95:
    status = "🟢 GREEN"
elif dqa_score >= 80:
    status = "🟡 YELLOW"
else:
    status = "🔴 RED"

a, b, c, d = st.columns(4)
a.metric("Records", f"{total_rows:,}")
b.metric("Duplicates", f"{duplicates:,}")
c.metric("DQA Score", f"{dqa_score:.2f}%")
d.metric("Status", status)

st.markdown("### Missingness (key fields)")
st.dataframe(missing_key.to_frame("missing_count"), use_container_width=True)

st.markdown("### Validity checks (key clinical fields)")
st.write(f"- Birth weight out of range (<300 or >5500g): **{bw_out_of_range:,}**")
st.write(f"- Gestational age out of range (<20 or >44 weeks): **{ga_out_of_range:,}**")

# ------------------------
# CATEGORY DISTRIBUTIONS (based on current scope)
# ------------------------
st.subheader("4) Birth weight & gestational age categories")

left, right = st.columns(2)

with left:
    st.markdown("#### Birth weight categories")
    bw_counts = data["bw_cat"].value_counts()
    st.dataframe(bw_counts.to_frame("count"), use_container_width=True)

    fig = plt.figure()
    bw_counts.plot(kind="bar")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Count")
    st.pyplot(fig)

with right:
    st.markdown("#### Gestational age categories")
    ga_counts = data["ga_cat"].value_counts()
    st.dataframe(ga_counts.to_frame("count"), use_container_width=True)

    fig = plt.figure()
    ga_counts.plot(kind="bar")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Count")
    st.pyplot(fig)

# ------------------------
# INTERVENTIONS & OUTCOMES
# ------------------------
st.subheader("5) Interventions and outcomes (by BW/GA categories)")

def yes_rate(series):
    if series is None:
        return None
    s = series.astype(str).str.strip().str.lower()
    return (s == "yes").mean() * 100

def death_rate(series):
    if series is None:
        return None
    s = series.astype(str).str.strip().str.lower()
    return (s == "dead").mean() * 100

tab1, tab2 = st.tabs(["By Birth weight", "By Gestational age"])

with tab1:
    grp = data.groupby("bw_cat", dropna=False)
    summary = pd.DataFrame({"n": grp.size()})

    if cpap_col != "(None)":
        summary["CPAP yes (%)"] = grp[cpap_col].apply(yes_rate)
    if kmc_col != "(None)":
        summary["KMC yes (%)"] = grp[kmc_col].apply(yes_rate)
    if outcome_col != "(None)":
        summary["Death (%)"] = grp[outcome_col].apply(death_rate)

    st.dataframe(summary, use_container_width=True)

with tab2:
    grp = data.groupby("ga_cat", dropna=False)
    summary = pd.DataFrame({"n": grp.size()})

    if cpap_col != "(None)":
        summary["CPAP yes (%)"] = grp[cpap_col].apply(yes_rate)
    if kmc_col != "(None)":
        summary["KMC yes (%)"] = grp[kmc_col].apply(yes_rate)
    if outcome_col != "(None)":
        summary["Death (%)"] = grp[outcome_col].apply(death_rate)

    st.dataframe(summary, use_container_width=True)

# ------------------------
# FACILITY LEVEL DQA (always from full dataset)
# ------------------------
st.subheader("6) Facility-level DQA (ranking)")

fac_table = work.groupby(facility_col).apply(
    lambda g: pd.Series({
        "records": len(g),
        "BW missing (%)": g[bw_col].isna().mean() * 100,
        "GA missing (%)": g[ga_col].isna().mean() * 100,
        "BW out-of-range (n)": int(((pd.to_numeric(g[bw_col], errors="coerce") < 300) |
                                   (pd.to_numeric(g[bw_col], errors="coerce") > 5500)).sum()),
        "GA out-of-range (n)": int(((pd.to_numeric(g[ga_col], errors="coerce") < 20) |
                                   (pd.to_numeric(g[ga_col], errors="coerce") > 44)).sum()),
    })
).sort_values("records", ascending=False)

st.dataframe(fac_table, use_container_width=True)

# ------------------------
# DOWNLOAD REPORT (scoped)
# ------------------------
st.subheader("7) Download outputs")

filename = "NEST360_DQA_Report.xlsx"
if mode == "Single facility (facility report)":
    safe_name = "".join(ch for ch in selected_facility if ch.isalnum() or ch in [" ", "_", "-"]).strip()
    filename = f"NEST360_DQA_Report_{safe_name}.xlsx"

output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    data.to_excel(writer, index=False, sheet_name="data_with_categories")
    missing_key.to_frame("missing_count").to_excel(writer, sheet_name="missing_key_fields")
    fac_table.to_excel(writer, sheet_name="facility_dqa")
    pd.DataFrame([{
        "scope": "single_facility" if mode == "Single facility (facility report)" else "all_facilities",
        "facility": selected_facility if mode == "Single facility (facility report)" else "ALL",
        "records": total_rows,
        "duplicates": duplicates,
        "missing_key_total": missing_key_total,
        "bw_out_of_range": bw_out_of_range,
        "ga_out_of_range": ga_out_of_range,
        "dqa_score": round(dqa_score, 2),
        "status": status
    }]).to_excel(writer, index=False, sheet_name="summary")

st.download_button(
    "Download DQA workbook (Excel)",
    data=output.getvalue(),
    file_name=filename,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

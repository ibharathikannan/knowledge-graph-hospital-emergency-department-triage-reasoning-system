"""
Streamlit UI: input a patient, see the knowledge graph reason about them.
Run: streamlit run app.py
"""
import streamlit as st

from ed_triage.knowledge_graph import build_graph
from ed_triage.rule_engine import fire, resolve
from ed_triage.validators import run_all

st.set_page_config(page_title="ED Triage Reasoning", layout="wide")
st.title("ED Triage Reasoning System")

st.header("Patient")
severity = st.slider("Severity score", 0.0, 1.0, 0.5, 0.01)
spo2 = st.number_input("SpO2 (%)", min_value=50, max_value=100, value=97)
age = st.number_input("Age", min_value=0, max_value=120, value=50)

patient = {"severity": severity, "spo2": spo2, "age": age}

st.header("Bed availability")
icu_beds = st.number_input("ICU beds free", min_value=0, max_value=20, value=2)
ward_beds = st.number_input("Ward beds free", min_value=0, max_value=50, value=5)

bed_state = {"ICU": icu_beds, "Ward": ward_beds}

g = build_graph()
fired = fire(g, patient)
decision = resolve(g, fired)

st.header("Result")
if decision.disposition:
    st.subheader(decision.disposition)
    for rule_id in decision.winning_rules:
        st.write(f"- **{rule_id}**: {g.nodes[rule_id]['description']}")
else:
    st.subheader("No rule fired")

st.header("Validation")
checks = run_all(g, decision, bed_state)
for check in checks:
    icon = "✅" if check.passed else "❌"
    st.write(f"{icon} **{check.name}** — {check.reason}")
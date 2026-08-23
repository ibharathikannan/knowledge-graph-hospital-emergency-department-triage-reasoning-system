"""
Streamlit UI: input a patient, see the knowledge graph reason about them.
Run: streamlit run app.py
"""
import streamlit as st
import matplotlib.pyplot as plt

from ed_triage.knowledge_graph import build_graph
from ed_triage.rule_engine import fire, resolve
from ed_triage.validators import run_all
from ed_triage.explanation import explain, summarize
from streamlit_agraph import agraph
from ed_triage.graph_viz import build_agraph
from ed_triage.predict import predict_severity

st.set_page_config(page_title="ED Triage Reasoning", layout="wide")
st.title("ED Triage Reasoning System")

st.markdown(
    """
    <style>
    iframe[data-testid="stCustomComponentV1"] {
        margin-left: 0 !important;
        margin-right: auto !important;
        display: block !important;
    }
    @media (max-width: 768px) {
        iframe[data-testid="stCustomComponentV1"] {
            transform: scale(0.55);
            transform-origin: top left;
            margin-bottom: -338px;  /* pulls up the blank space the scale leaves behind */
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

respiratory_rate = st.number_input("Respiratory rate (breaths/min)", min_value=8, max_value=40, value=18)
spo2 = st.number_input("SpO2 (%)", min_value=50, max_value=100, value=97)
heart_rate = st.number_input("Heart rate (bpm)", min_value=30, max_value=200, value=80)
systolic_bp = st.number_input("Systolic BP (mmHg)", min_value=60, max_value=220, value=120)
temperature = st.number_input("Temperature (°C)", min_value=33.0, max_value=42.0, value=37.0, step=0.1)
age = st.number_input("Age", min_value=0, max_value=120, value=50)

vitals = {
    "respiratory_rate": respiratory_rate,
    "spo2": spo2,
    "heart_rate": heart_rate,
    "systolic_bp": systolic_bp,
    "temperature": temperature,
    "age": age,
}
severity = predict_severity(vitals)
st.metric("Predicted severity", f"{severity:.2f}")

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
    factors = explain(g, patient, decision)
    st.write(summarize(decision, factors))
    for f in factors:
        st.write(f"- {f.as_text()}")
else:
    st.subheader("No rule fired")

st.header("Validation")
checks = run_all(g, decision, bed_state)
for check in checks:
    icon = "✅" if check.passed else "❌"
    st.write(f"{icon} **{check.name}** — {check.reason}")


st.header("Reasoning graph")
beaten = [r for r in fired if r not in decision.winning_rules]
st.caption(f"🟡 fired but overridden: {beaten or 'none'}  |  🔴 winning: {decision.winning_rules}")
nodes, edges, config = build_agraph(g, fired=fired, winning=decision.winning_rules)
agraph(nodes=nodes, edges=edges, config=config)

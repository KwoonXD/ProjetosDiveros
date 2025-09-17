import json, datetime as dt
import streamlit as st

from utils.jira_api import JiraClient
from utils.messages import build_briefing

st.set_page_config(page_title="FS – Briefings por Data", layout="wide")
st.title("📌 FS – Briefings do Técnico (agrupados por data)")

with st.sidebar:
    st.header("Configurações")
    base_url = st.text_input("Base URL", "https://delfia.atlassian.net")
    email = st.text_input("E-mail", "wt@parceiro.delfia.tech")
    token = st.text_input("API Token", type="password")
    project_key = st.text_input("Projeto", "FS")
    jql = st.text_area("JQL", f"project = {project_key} AND statusCategory != Done ORDER BY created DESC")
    fmap_file = st.file_uploader("fieldmap.json", type="json")

if not (base_url and email and token and fmap_file):
    st.warning("Configure as credenciais e faça upload do fieldmap.json")
    st.stop()

fmap = json.load(fmap_file)
jira = JiraClient(base_url, email, token)

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Data inicial", dt.date.today() - dt.timedelta(days=7))
with col2:
    end_date = st.date_input("Data final", dt.date.today() + dt.timedelta(days=7))

with st.spinner("Carregando chamados..."):
    issues = list(jira.search_all(jql, fields=None))

items = []
for issue in issues:
    briefing = build_briefing(issue, fmap, JiraClient.pick_display)
    fields = issue.get("fields", {})
    data_ag = fields.get(fmap.get("data_agendamento")) or fields.get("created")
    try:
        gdate = dt.date.fromisoformat(str(data_ag)[:10])
    except Exception:
        gdate = None
    if gdate and (gdate < start_date or gdate > end_date):
        continue
    items.append((gdate, issue["key"], briefing))

items.sort(key=lambda x: (x[0] or dt.date.min, x[1]))

for gdate, key, briefing in items:
    label = gdate.strftime("%d/%m/%Y") if gdate else "Sem data"
    with st.expander(f"📅 {label} – {key}", expanded=False):
        st.text_area("Script", value=briefing, height=300, key=f"ta_{key}")
        st.download_button("Baixar TXT", briefing.encode("utf-8"), file_name=f"{key}.txt", mime="text/plain")

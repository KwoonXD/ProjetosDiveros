# --- path fix ---
import os, sys
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)
# ---------------

import json, datetime as dt
import streamlit as st

from utils.jira_api import JiraClient
from utils.messages import build_briefing

st.set_page_config(page_title="FS – Briefings por Data", layout="wide")
st.title("📌 FS – Briefings do Técnico (agrupados por data)")

# Sidebar
with st.sidebar:
    st.header("Configurações")
    base_url = st.text_input("Base URL", "https://delfia.atlassian.net")
    email = st.text_input("E-mail", "wt@parceiro.delfia.tech")
    token = st.text_input("API Token", type="password")
    project_key = st.text_input("Projeto", "FS")
    jql_default = f"project = {project_key} AND statusCategory != Done ORDER BY created DESC"
    jql = st.text_area("JQL", jql_default, height=80)
    fmap_file = st.file_uploader("fieldmap.json (customfields do FS)", type="json")

if not (base_url and email and token):
    st.warning("Informe base URL, e-mail e token.")
    st.stop()

jira = JiraClient(base_url, email, token)

# ---- Descobrir IDs de campos (dump por issue) ----
with st.expander("🔎 Descobrir IDs (cole um issue, ex.: FS-8877)"):
    issue_key = st.text_input("Issue key", value="", placeholder="FS-8877")
    if st.button("Dump de campos", type="primary", disabled=not issue_key):
        try:
            report, _issue = jira.dump_fields(issue_key.strip())
            st.code(report, language="text")
            st.success("Use as colunas da esquerda (customfield_xxxxx) no seu fieldmap.json.")
        except Exception as e:
            st.error(f"Falha no dump: {e}")

# --- filtros de datas e upload do fieldmap (para formatar os briefings) ---
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Data inicial", dt.date.today() - dt.timedelta(days=7))
with col2:
    end_date = st.date_input("Data final", dt.date.today() + dt.timedelta(days=14))

if fmap_file is None:
    st.info("Faça upload do seu fieldmap.json para formatar os briefings.")
    st.stop()

fmap = json.load(fmap_file)

# Buscar issues (com os 4 modos do cliente novo)
try:
    with st.spinner("Carregando chamados..."):
        issues = list(jira.search_all(jql, fields=None, page_size=100))
except Exception as e:
    st.error(f"Falha ao consultar o Jira: {e}")
    st.stop()

# Filtrar e agrupar por data (agendamento -> created)
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
    items.append((gdate, issue.get("key", ""), briefing))

items.sort(key=lambda x: (x[0] or dt.date.min, x[1]))

# Render
if not items:
    st.info("Nenhum chamado encontrado com os filtros atuais.")
else:
    from itertools import groupby
    def kf(row): return row[0] or dt.date.min
    for day, group in groupby(items, key=kf):
        label = (day.strftime("%d/%m/%Y") if day != dt.date.min else "Sem data")
        group = list(group)
        with st.expander(f"📅 {label} — {len(group)} chamado(s)", expanded=True):
            for gdate, key, briefing in group:
                st.markdown(f"### {key}")
                st.text_area("Script do técnico", value=briefing, height=300, key=f"ta_{key}")
                st.download_button("Baixar TXT", briefing.encode("utf-8"),
                                   file_name=f"{key}.txt", mime="text/plain", key=f"dl_{key}")
                st.divider()

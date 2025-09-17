# --- path fix ---
import os, sys
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
if APP_ROOT not in sys.path: sys.path.insert(0, APP_ROOT)
# ---------------

import json, datetime as dt
import streamlit as st
from itertools import groupby

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
    jql = st.text_area(
        "JQL (usado quando houver acesso core)",
        f"project = {project_key} AND statusCategory != Done ORDER BY created DESC",
        height=80,
    )
    force_core = st.toggle("Forçar API Core (JQL)", value=True,
                           help="Ignora JSM e usa apenas /rest/api/3/search")
    fmap_file = st.file_uploader("fieldmap.json (customfields do FS)", type="json")

if not (base_url and email and token):
    st.warning("Informe base URL, e-mail e token.")
    st.stop()

jira = JiraClient(base_url, email, token)

# Diagnóstico
with st.expander("🧪 Diagnóstico de autenticação (API Core / JSM)", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        code, body = jira.diag_core()
        st.write("**/rest/api/3/myself** →", code)
        st.code(body or "(vazio)", language="json")
    with c2:
        code, body = jira.diag_jsm()
        st.write("**/rest/servicedeskapi/servicedesk** →", code)
        st.code(body or "(vazio)", language="json")

# Filtros
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Data inicial", dt.date.today() - dt.timedelta(days=7))
with col2:
    end_date = st.date_input("Data final", dt.date.today() + dt.timedelta(days=14))

if fmap_file is None:
    st.info("Faça upload do seu fieldmap.json para formatar os briefings.")
    st.stop()

# Carregar fieldmap
try:
    fmap = json.load(fmap_file)
except Exception as e:
    st.error(f"Seu fieldmap.json não é um JSON válido: {e}")
    st.stop()

# Buscar issues
try:
    with st.spinner("Carregando chamados..."):
        issues = list(jira.search_all(project_key, jql=jql, fields=None,
                                      page_size=100, force_core=force_core))
except Exception as e:
    st.error(f"Falha ao consultar: {e}")
    st.stop()

# Agrupar por data
items = []
for issue in issues:
    fields = issue.get("fields", {}) or {}
    data_ag = fields.get(fmap.get("data_agendamento")) or fields.get("created")
    try:
        gdate = dt.date.fromisoformat(str(data_ag)[:10])
    except Exception:
        gdate = None
    if gdate and (gdate < start_date or gdate > end_date):
        continue
    briefing = build_briefing(issue, fmap, lambda v: v if isinstance(v, str) else str(v))
    items.append((gdate, issue.get("key", ""), briefing))

items.sort(key=lambda x: (x[0] or dt.date.min, x[1]))

# Render
if not items:
    st.info("Nenhum chamado encontrado com os filtros atuais.")
else:
    def keyfunc(row): return row[0] or dt.date.min
    for day, group in groupby(items, key=keyfunc):
        label = (day.strftime("%d/%m/%Y") if day != dt.date.min else "Sem data")
        group = list(group)
        with st.expander(f"📅 {label} — {len(group)} chamado(s)", expanded=True):
            for gdate, key, briefing in group:
                st.markdown(f"### {key}")
                st.text_area("Script do técnico", value=briefing, height=300, key=f"ta_{key}")
                st.download_button("Baixar TXT", briefing.encode("utf-8"),
                                   file_name=f"{key}.txt", mime="text/plain", key=f"dl_{key}")
                st.divider()

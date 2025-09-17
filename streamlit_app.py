# --- FIX de path para garantir que utils seja encontrado ---
import os, sys
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)
# -----------------------------------------------------------

import json, datetime as dt
import streamlit as st

from utils.jira_api import JiraClient
from utils.messages import build_briefing

st.set_page_config(page_title="FS – Briefings por Data", layout="wide")
st.title("📌 FS – Briefings do Técnico (agrupados por data)")

# Sidebar - configurações
with st.sidebar:
    st.header("Configurações")
    base_url = st.text_input("Base URL", "https://delfia.atlassian.net")
    email = st.text_input("E-mail", "wt@parceiro.delfia.tech")
    token = st.text_input("API Token", type="password")
    project_key = st.text_input("Projeto", "FS")
    jql_default = f"project = {project_key} AND statusCategory != Done ORDER BY created DESC"
    jql = st.text_area("JQL", jql_default, height=80)
    fmap_file = st.file_uploader("fieldmap.json (customfields do FS)", type="json")

if not (base_url and email and token and fmap_file):
    st.warning("Configure as credenciais e faça upload do fieldmap.json")
    st.stop()

# Carregar mapeamento
fmap = json.load(fmap_file)

# Filtros de datas
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Data inicial", dt.date.today() - dt.timedelta(days=7))
with col2:
    end_date = st.date_input("Data final", dt.date.today() + dt.timedelta(days=14))

jira = JiraClient(base_url, email, token)

# Buscar issues com tratamento de erro de API
try:
    with st.spinner("Carregando chamados..."):
        issues = list(jira.search_all(jql, fields=None, page_size=100))
except Exception as e:
    st.error(f"Falha ao consultar o Jira: {e}")
    st.stop()

items = []
for issue in issues:
    briefing = build_briefing(issue, fmap, JiraClient.pick_display)

    fields = issue.get("fields", {})
    # prioridade: data_agendamento -> created
    data_ag = fields.get(fmap.get("data_agendamento")) or fields.get("created")

    try:
        gdate = dt.date.fromisoformat(str(data_ag)[:10])
    except Exception:
        gdate = None

    if gdate and (gdate < start_date or gdate > end_date):
        continue

    items.append((gdate, issue.get("key", ""), briefing))

# Ordenação por data e chave
items.sort(key=lambda x: (x[0] or dt.date.min, x[1]))

# Renderização
if not items:
    st.info("Nenhum chamado encontrado com os filtros atuais.")
else:
    # Agrupar por dia
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

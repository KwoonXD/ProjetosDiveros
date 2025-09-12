import json
import streamlit as st
import pandas as pd
from utils.jira_api import jql_search, ping_me

st.set_page_config(page_title="Field Service", page_icon="🛠️", layout="wide")

# Sidebar: seleção de projeto do fieldmap
@st.cache_data
def load_fieldmap():
    with open("config/fieldmap.json", "r", encoding="utf-8") as f:
        return json.load(f)
FIELD_MAP = load_fieldmap()
PROJETOS = list(FIELD_MAP["projetos"].keys())
DEFAULT = FIELD_MAP.get("padrao", PROJETOS[0] if PROJETOS else None)
proj_name = st.sidebar.selectbox("Projeto (fieldmap)", PROJETOS, index=PROJETOS.index(DEFAULT))

proj_cfg = FIELD_MAP["projetos"][proj_name]
project_key = proj_cfg["project_key"]
statuses_map = proj_cfg["statuses"]
fields = proj_cfg["fields"]

st.sidebar.markdown("### Diagnóstico")
if st.sidebar.button("Testar credenciais (myself)"):
    ok, data = ping_me()
    st.sidebar.write("OK ✅" if ok else "Falhou ❌")
    st.sidebar.json(data)

tab1, tab2, tab3 = st.tabs(["📋 Chamados", "📊 Visão Geral", "🧭 Descoberta"])

with tab1:
    st.subheader("Chamados")
    try:
        jql = f'project = {project_key} AND statusCategory != Done ORDER BY created DESC'
        issues = jql_search(jql)
        rows = []
        for it in issues:
            key = it["key"]
            sf = it["fields"]
            loja = None
            if fields.get("store"):
                loja_field = sf.get(fields["store"])
                loja = loja_field.get("value") if isinstance(loja_field, dict) else loja_field
            rows.append({
                "Chamado": key,
                "Resumo": sf.get("summary"),
                "Status": sf.get("status", {}).get("name"),
                "Loja": loja
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        st.caption(f"{len(df)} issues")
    except Exception as e:
        st.error(f"Erro ao listar chamados: {e}")

with tab2:
    st.subheader("Visão Geral")
    st.write("KPIs simples de exemplo (conte os status mapeados).")
    try:
        nomes_status = sum(statuses_map.values(), [])
        jql = f'project = {project_key} AND status in ("' + '","'.join(nomes_status) + '")'
        issues = jql_search(jql)
        df = pd.DataFrame([{"status": it["fields"]["status"]["name"]} for it in issues])
        if not df.empty:
            st.metric("Total (status mapeados)", len(df))
            st.bar_chart(df.value_counts("status"))
        else:
            st.info("Nenhuma issue nos status mapeados.")
    except Exception as e:
        st.error(f"Erro na visão geral: {e}")

with tab3:
    st.subheader("Descoberta")
    st.write("Use para inspecionar status e descobrir customfields rapidamente.")
    q = st.text_input("JQL", value=f"project = {project_key} ORDER BY created DESC", label_visibility="collapsed")
    if st.button("Executar JQL"):
        try:
            issues = jql_search(q)
            st.write(f"Retornou {len(issues)} issues")
            if issues:
                st.json(issues[0]["fields"])  # inspeção rápida do 1º resultado
        except Exception as e:
            st.error(f"Erro: {e}")

# streamlit_app.py
import json
import re
import os
import sys
import streamlit as st
import pandas as pd
from utils.jira_api import jql_search, ping_me

# Garante que o diretório do app esteja no sys.path
sys.path.append(os.path.dirname(__file__))

st.set_page_config(page_title="Field Service", page_icon="🛠️", layout="wide")

# ---------- Util: sanitizador simples p/ JSON com comentários/trailing commas ----------
def _strip_json_comments_and_trailing_commas(text: str) -> str:
    # remove //... e /* ... */
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # remove vírgulas à direita antes de } ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text.strip()

# ---------- Fieldmap loader com tratamento de erros ----------
@st.cache_data
def load_fieldmap():
    path = os.path.join("config", "fieldmap.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    try:
        # tenta direto
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # tenta sanitizar (remove comentários e trailing commas)
        cleaned = _strip_json_comments_and_trailing_commas(raw)
        try:
            data = json.loads(cleaned)
            # avisa que foi sanitizado
            st.warning(
                "O `config/fieldmap.json` tinha comentários ou vírgulas sobrando. "
                "Consegui ler após sanitizar. Ideal corrigir o arquivo na origem."
            )
            return data
        except json.JSONDecodeError as e2:
            # propaga erro explicativo
            raise ValueError(
                "Não foi possível carregar `config/fieldmap.json` (JSON inválido). "
                f"Tente validar o arquivo. Erro bruto: {e2}"
            )

# ---------- Fallback padrão caso o JSON quebrou ----------
DEFAULT_FIELDMAP = {
    "projetos": {
        "NOVO": {
            "project_key": "ABC",
            "statuses": {
                "AGENDAMENTO": ["AGENDAMENTO", "Agendamento"],
                "AGENDADO": ["Agendado"],
                "TEC_CAMPO": ["TEC-CAMPO", "Técnico em campo"]
            },
            "fields": {
                "store": "customfield_xxxxx",
                "pdv": "customfield_xxxxx",
                "asset": "customfield_xxxxx",
                "problem": "customfield_xxxxx",
                "address": "customfield_xxxxx",
                "state": "customfield_xxxxx",
                "zipcode": "customfield_xxxxx",
                "city": "customfield_xxxxx",
                "scheduled_date": "customfield_xxxxx"
            }
        }
    },
    "padrao": "NOVO"
}

# ---------- Tenta carregar o fieldmap de verdade; se falhar, mostra erro e usa fallback ----------
try:
    FIELD_MAP = load_fieldmap()
except Exception as e:
    st.error(f"Falha ao ler `config/fieldmap.json`: {e}")
    st.info("Usando configuração padrão temporária (fallback) só para o app abrir.")
    FIELD_MAP = DEFAULT_FIELDMAP

PROJETOS = list(FIELD_MAP.get("projetos", {}).keys())
if not PROJETOS:
    st.stop()

DEFAULT = FIELD_MAP.get("padrao", PROJETOS[0])
proj_name = st.sidebar.selectbox("Projeto (fieldmap)", PROJETOS, index=PROJETOS.index(DEFAULT))

proj_cfg = FIELD_MAP["projetos"][proj_name]
project_key = proj_cfg.get("project_key", "ABC")
statuses_map = proj_cfg.get("statuses", {})
fields = proj_cfg.get("fields", {})

# ---------- Sidebar: diagnóstico ----------
st.sidebar.markdown("### Diagnóstico")
if st.sidebar.button("Testar credenciais (myself)"):
    ok, data = ping_me()
    st.sidebar.write("OK ✅" if ok else "Falhou ❌")
    st.sidebar.json(data)

# ---------- Abas ----------
tab1, tab2, tab3 = st.tabs(["📋 Chamados", "📊 Visão Geral", "🧭 Descoberta"])

with tab1:
    st.subheader("Chamados")
    try:
        jql = f'project = {project_key} AND statusCategory != Done ORDER BY created DESC'
        issues = jql_search(jql)
        rows = []
        for it in issues:
            key = it.get("key")
            sf = it.get("fields", {})
            loja = None
            if fields.get("store"):
                loja_field = sf.get(fields["store"])
                if isinstance(loja_field, dict) and "value" in loja_field:
                    loja = loja_field.get("value")
                else:
                    loja = loja_field
            rows.append({
                "Chamado": key,
                "Resumo": sf.get("summary"),
                "Status": (sf.get("status") or {}).get("name"),
                "Loja": loja
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        st.caption(f"{len(df)} issues")
    except Exception as e:
        st.error(f"Erro ao listar chamados: {e}")

with tab2:
    st.subheader("Visão Geral")
    try:
        nomes_status = sum(statuses_map.values(), [])
        if nomes_status:
            jql = f'project = {project_key} AND status in ("' + '","'.join(nomes_status) + '")'
        else:
            jql = f'project = {project_key}'
        issues = jql_search(jql)
        df = pd.DataFrame([{"status": (it.get("fields", {}).get("status") or {}).get("name")} for it in issues])
        if not df.empty and "status" in df:
            st.metric("Total (status mapeados)", len(df))
            st.bar_chart(df.value_counts("status"))
        else:
            st.info("Nenhuma issue para os status mapeados, ou status não encontrado.")
    except Exception as e:
        st.error(f"Erro na visão geral: {e}")

with tab3:
    st.subheader("Descoberta")
    st.write("Use para inspecionar status e descobrir customfields rapidamente.")
    q = st.text_inp_

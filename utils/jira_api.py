# utils/jira_api.py
import requests
import streamlit as st

def _secrets():
    """
    Lê as credenciais e configurações do arquivo .streamlit/secrets.toml
    """
    cfg = st.secrets["JIRA"]
    return {
        "email": cfg["EMAIL"],
        "token": cfg["API_TOKEN"],
        "cloud_id": cfg.get("CLOUD_ID", ""),
        "use_ex": bool(cfg.get("USE_EX_API", True)),
        "subdomain": cfg.get("SITE_SUBDOMAIN", ""),
        "timeout": int(cfg.get("TIMEOUT_SECS", 30)),
        "page_size": int(cfg.get("PAGE_SIZE", 100)),
    }

def _base_url():
    """
    Monta a URL base de acordo com a configuração (EX API ou domínio do Jira).
    """
    s = _secrets()
    if s["use_ex"]:
        return f"https://api.atlassian.com/ex/jira/{s['cloud_id']}/rest/api/3"
    return f"https://{s['subdomain']}.atlassian.net/rest/api/3"

def jql_search(jql: str):
    """
    Executa uma busca no Jira via JQL, com paginação.
    Retorna a lista de issues completas.
    """
    s = _secrets()
    auth = (s["email"], s["token"])
    base = _base_url()
    start_at = 0
    issues = []

    while True:
        params = {"jql": jql, "startAt": start_at, "maxResults": s["page_size"]}
        r = requests.get(f"{base}/search", params=params, auth=auth, timeout=s["timeout"])
        if not r.ok:
            raise RuntimeError(f"Jira search error ({r.status_code}): {r.text}")
        data = r.json()
        issues.extend(data.get("issues", []))
        total = data.get("total", 0)
        start_at += s["page_size"]
        if start_at >= total:
            break
    return issues

def ping_me():
    """
    Testa conexão com Jira usando o endpoint /myself
    Retorna (True, json) se sucesso ou (False, erro) se falhou.
    """
    s = _secrets()
    auth = (s["email"], s["token"])
    base = _base_url()
    r = requests.get(f"{base}/myself", auth=auth, timeout=s["timeout"])
    if not r.ok:
        return False, f"{r.status_code}: {r.text}"
    return True, r.json()

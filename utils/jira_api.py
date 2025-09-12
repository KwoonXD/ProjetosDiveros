# utils/jira_api.py
import requests
import streamlit as st

def _secrets():
    if "JIRA" not in st.secrets:
        raise KeyError('st.secrets has no key "JIRA". Configure a seção [JIRA] nos Secrets.')
    cfg = st.secrets["JIRA"]
    return {
        "email": cfg["EMAIL"],
        "token": cfg["API_TOKEN"],
        "use_ex": bool(cfg.get("USE_EX_API", True)),
        "cloud_id": cfg.get("CLOUD_ID", ""),
        "subdomain": cfg.get("SITE_SUBDOMAIN", ""),
        "timeout": int(cfg.get("TIMEOUT_SECS", 30)),
        "page_size": int(cfg.get("PAGE_SIZE", 100)),
    }

def _base_url():
    s = _secrets()
    if s["use_ex"]:
        if not s["cloud_id"]:
            raise ValueError("USE_EX_API=true, mas CLOUD_ID está vazio.")
        return f"https://api.atlassian.com/ex/jira/{s['cloud_id']}/rest/api/3"
    else:
        if not s["subdomain"]:
            raise ValueError("USE_EX_API=false, mas SITE_SUBDOMAIN está vazio.")
        return f"https://{s['subdomain']}.atlassian.net/rest/api/3"

def _auth_tuple():
    s = _secrets()
    return (s["email"], s["token"])

def _headers_json():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def ping_me():
    """
    Testa credenciais no endpoint /myself.
    Retorna (ok: bool, payload_or_msg)
    """
    s = _secrets()
    url = f"{_base_url()}/myself"
    try:
        r = requests.get(url, auth=_auth_tuple(), headers={"Accept": "application/json"}, timeout=s["timeout"])
    except Exception as e:
        return False, f"Falha de rede ao chamar {url}: {e}"

    if r.status_code == 401:
        return False, f"401 Unauthorized. Verifique EMAIL/API_TOKEN e acesso do usuário. Corpo: {r.text}"
    if not r.ok:
        return False, f"{r.status_code} {r.reason}. Corpo: {r.text}"

    try:
        return True, r.json()
    except Exception:
        return False, f"Resposta não-JSON de /myself: {r.text[:300]}"

# ---------- Implementações de busca ----------

def _search_legacy(jql: str, start_at: int, page_size: int):
    """
    GET /rest/api/3/search?jql=...  (LEGADO)
    Retorna (status_code, data_text, data_json_ou_None)
    """
    s = _secrets()
    base = _base_url()
    params = {"jql": jql, "startAt": start_at, "maxResults": page_size}
    r = requests.get(f"{base}/search", params=params, auth=_auth_tuple(),
                     headers={"Accept": "application/json"}, timeout=s["timeout"])
    try:
        data_json = r.json()
    except Exception:
        data_json = None
    return r.status_code, r.text, data_json

def _search_new_batch(jql: str, start_at: int, page_size: int):
    """
    POST /rest/api/3/search/jql (NOVA)
    A nova API aceita queries em lote.
    Corpo esperado (forma simplificada e compatível):
      {
        "queries": [
          {
            "query": "project = ABC ORDER BY created DESC",
            "startAt": 0,
            "maxResults": 100
          }
        ]
      }

    A resposta típica vem como:
      {
        "responses": [
          {
            "results": [...],
            "total": 123
          }
        ]
      }
    """
    s = _secrets()
    base = _base_url()
    payload = {
        "queries": [
            {
                "query": jql,
                "startAt": start_at,
                "maxResults": page_size
                # campos extras poderiam ser adicionados aqui, ex.: "fields": ["summary","status","*all"]
            }
        ]
    }
    r = requests.post(f"{base}/search/jql", json=payload, auth=_auth_tuple(),
                      headers=_headers_json(), timeout=s["timeout"])

    if r.status_code == 401:
        raise RuntimeError(
            "Jira search error (401 Unauthorized) na /search/jql. "
            "Cheque EMAIL/API_TOKEN, permissões e CLOUD_ID (se EX API). "
            f"Corpo: {r.text}"
        )
    if r.status_code == 404:
        # Alguns tenants antigos podem não ter /search/jql; improvável após migração, mas tratamos.
        raise RuntimeError("Endpoint /search/jql não encontrado (404). Verifique versão/tenant.")

    if not r.ok:
        raise RuntimeError(f"Jira search error ({r.status_code}) na /search/jql: {r.text}")

    data = r.json()
    responses = data.get("responses", [])
    if not responses:
        return [], 0

    first = responses[0]
    results = first.get("results", [])
    total = first.get("total", len(results))
    return results, total

def jql_search(jql: str):
    """
    Busca issues com paginação. Tenta LEGACY e, se vier 410, usa NEW /search/jql.
    Retorna lista de issues (dicts do Jira).
    """
    s = _secrets()
    page_size = s["page_size"]
    issues = []
    start_at = 0

    # Primeiro tentamos LEGACY; se vier 410, trocamos para NEW.
    use_new = False

    while True:
        if not use_new:
            status, text, data = _search_legacy(jql, start_at, page_size)
            if status == 410:
                # API legacy removida no tenant → ligar modo novo
                use_new = True
            elif status == 401:
                raise RuntimeError(
                    "Jira search error (401 Unauthorized) na /search. "
                    "Cheque EMAIL/API_TOKEN, permissões e CLOUD_ID (se EX API). "
                    f"Corpo: {text}"
                )
            elif status >= 400:
                raise RuntimeError(f"Jira search error ({status}) na /search: {text}")
            else:
                # sucesso no legacy
                batch = (data or {}).get("issues", [])
                total = (data or {}).get("total", len(batch))
                issues.extend(batch)
                start_at += page_size
                if start_at >= total:
                    break
                continue  # próxima página pelo legacy

        # Modo novo (/search/jql)
        batch, total = _search_new_batch(jql, start_at, page_size)
        issues.extend(batch)
        start_at += page_size
        if start_at >= total:
            break

    return issues

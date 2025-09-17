import base64
import datetime as dt
import requests
from typing import Dict, List, Tuple, Optional

class JiraClient:
    """
    Cliente híbrido:
    - Tenta primeiro APIs 'core' (/rest/api/3)
    - Se não tiver permissão, cai nas APIs JSM (/rest/servicedeskapi)
    """
    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        token = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Basic {token}",
        })
        self._mode_core_ok: Optional[bool] = None
        self._cached_sd_by_key: Dict[str, dict] = {}

    # ------------- helpers -------------
    def _post(self, path: str, json: dict, timeout: int = 60):
        return self.session.post(f"{self.base_url}{path}", json=json, timeout=timeout)

    def _get(self, path: str, params: dict = None, timeout: int = 60):
        return self.session.get(f"{self.base_url}{path}", params=params, timeout=timeout)

    # ------------- capability check -------------
    def can_use_core(self) -> bool:
        """true se o usuário tem acesso às APIs core (/rest/api/3)."""
        if self._mode_core_ok is not None:
            return self._mode_core_ok
        r = self._get("/rest/api/3/myself")
        self._mode_core_ok = (r.status_code == 200)
        return self._mode_core_ok

    # ------------- CORE SEARCH (Software/Agent) -------------
    def _core_search_all(self, jql: str, fields=None, page_size: int = 100):
        """Usa o endpoint novo /rest/api/3/search/jql (payload moderno)."""
        start_at = 0
        while True:
            body = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": page_size
            }
            if fields is not None:
                body["fields"] = fields
            r = self._post("/rest/api/3/search/jql", body)
            if r.status_code != 200:
                raise RuntimeError(f"Jira search error ({r.status_code}): {r.text}")
            data = r.json()
            issues = data.get("issues", []) or []
            total = int(data.get("total", 0) or 0)
            if not issues:
                break
            for it in issues:
                yield it
            start_at += len(issues)
            if start_at >= total:
                break

    # ------------- JSM SEARCH (Customer/Agent) -------------
    def _get_service_desks(self) -> List[dict]:
        r = self._get("/rest/servicedeskapi/servicedesk")
        if r.status_code != 200:
            raise RuntimeError(f"JSM servicedesk error ({r.status_code}): {r.text}")
        data = r.json()
        return data.get("values", []) or []

    def _service_desk_by_project_key(self, project_key: str) -> dict:
        if project_key in self._cached_sd_by_key:
            return self._cached_sd_by_key[project_key]
        desks = self._get_service_desks()
        match = None
        for d in desks:
            # cloud retorna {id, projectId, projectKey, projectName, name, ...}
            if str(d.get("projectKey")).upper() == project_key.upper():
                match = d
                break
        if not match:
            # fallback: tenta por name
            for d in desks:
                if project_key.upper() in str(d.get("name", "")).upper():
                    match = d
                    break
        if not match:
            raise RuntimeError(f"Não encontrei Service Desk para o projeto '{project_key}'. Desks vistos: {[d.get('projectKey') for d in desks]}")
        self._cached_sd_by_key[project_key] = match
        return match

    def _jsm_list_requests(self, service_desk_id: str, start: int = 0, limit: int = 50):
        """
        GET /rest/servicedeskapi/request?serviceDeskId=...&requestStatus=all&expand=requestFieldValues
        """
        params = {
            "serviceDeskId": str(service_desk_id),
            "requestStatus": "all",
            "start": start,
            "limit": limit,
            "expand": "requestFieldValues"
        }
        r = self._get("/rest/servicedeskapi/request", params=params)
        if r.status_code != 200:
            raise RuntimeError(f"JSM request list error ({r.status_code}): {r.text}")
        return r.json()

    def _jsm_request_by_key(self, issue_key: str):
        r = self._get(f"/rest/servicedeskapi/request/{issue_key}", params={"expand":"requestFieldValues"})
        if r.status_code != 200:
            raise RuntimeError(f"JSM request error ({r.status_code}): {r.text}")
        return r.json()

    # ------------- PUBLIC API -------------
    def search_all(self, project_key: str, jql: str = None, fields=None, page_size: int = 100):
        """
        Itera por todos os chamados do projeto.
        - Se tiver acesso 'core': usa JQL (parâmetro jql).
        - Se NÃO tiver: lista as requests do Service Desk do projeto (customer-friendly).
        """
        if self.can_use_core():
            if not jql:
                jql = f"project = {project_key} ORDER BY created DESC"
            yield from self._core_search_all(jql, fields=fields, page_size=page_size)
            return

        # JSM (customer/agent sem licença core)
        sd = self._service_desk_by_project_key(project_key)
        sdid = sd.get("id")
        start = 0
        while True:
            data = self._jsm_list_requests(sdid, start=start, limit=page_size)
            values = data.get("values", []) or []
            if not values:
                break
            # Convertemos cada request JSM em um "issue-like" mínimo
            for req in values:
                issue_like = {
                    "key": req.get("issueIdOrKey"),
                    "fields": {
                        "summary": req.get("summary"),
                        "created": req.get("createdDate", {}).get("iso8601"),
                        # mapeia requestFieldValues -> dict simples por fieldId
                        **self._flatten_jsm_fields(req.get("requestFieldValues", []))
                    }
                }
                yield issue_like
            start += len(values)
            if start >= int(data.get("size", start)):
                break

    def _flatten_jsm_fields(self, rfv: List[dict]) -> Dict[str, str]:
        """
        Transforma requestFieldValues (JSM) em dict {<fieldId or name>: <value string>}
        """
        out = {}
        for f in rfv or []:
            fid = f.get("fieldId") or f.get("name") or f.get("label") or "unknown"
            val = f.get("value")
            # normaliza valor em string
            if isinstance(val, list):
                sval = ", ".join([str(v) for v in val])
            elif isinstance(val, dict):
                sval = val.get("name") or val.get("value") or str(val)
            else:
                sval = "" if val is None else str(val)
            out[fid] = sval
        return out

    def dump_fields(self, issue_key: str) -> Tuple[str, dict]:
        """
        Tenta /issue (core). Se 403/404, tenta /servicedeskapi/request/{key}.
        Retorna texto formatado + raw.
        """
        # CORE
        r = self._get(f"/rest/api/3/issue/{issue_key}", params={"expand":"names"})
        if r.status_code == 200:
            issue = r.json()
            names = issue.get("names", {}) or {}
            fields = issue.get("fields", {}) or {}
            lines = []
            for fid, val in fields.items():
                name = names.get(fid, fid)
                short = ""
                if isinstance(val, dict):
                    short = val.get("name") or val.get("value") or val.get("displayName") or str(val)[:160]
                elif isinstance(val, list):
                    short = f"list[{len(val)}]"
                else:
                    short = str(val)[:160]
                lines.append(f"{fid:>18} | {name:40} | {short}")
            lines.sort()
            return "\n".join(lines), issue
        elif r.status_code not in (403, 404):
            raise RuntimeError(f"Jira issue error ({r.status_code}): {r.text}")

        # JSM fallback
        req = self._jsm_request_by_key(issue_key)
        fields = self._flatten_jsm_fields(req.get("requestFieldValues", []))
        # monta um "report" simples com os IDs que vierem expostos como fieldId
        lines = []
        for fid, val in sorted(fields.items()):
            lines.append(f"{fid:>18} | requestField | {str(val)[:160]}")
        report = "\n".join(lines) if lines else "Nenhum campo retornado pelo servicedeskapi (verifique permissões/expansions)."
        # devolve um objeto 'issue-like'
        issue_like = {
            "key": issue_key,
            "fields": {
                "summary": req.get("summary"),
                "created": req.get("createdDate", {}).get("iso8601"),
                **fields
            }
        }
        return report, issue_like

    @staticmethod
    def pick_display(v):
        if v is None:
            return ""
        if isinstance(v, dict):
            for k in ("displayName", "name", "value", "emailAddress", "text"):
                if v.get(k):
                    return str(v[k])
            return str(v)
        if isinstance(v, list):
            return ", ".join([JiraClient.pick_display(item) for item in v])
        return str(v)

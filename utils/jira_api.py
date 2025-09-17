import base64
import requests
from typing import Dict, List, Optional, Tuple

class JiraClient:
    """
    Cliente híbrido:
      - Core (Jira Software/Work Management) via /rest/api/3/search
      - JSM (Service Management) via /rest/servicedeskapi/* quando necessário
    Tem diagnóstico embutido para verificar autenticação nas duas APIs.
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
        self._core_ok: Optional[bool] = None

    # ------------------ HTTP helpers ------------------
    def _post(self, path: str, json: dict, timeout: int = 60):
        return self.session.post(f"{self.base_url}{path}", json=json, timeout=timeout)

    def _get(self, path: str, params: dict = None, timeout: int = 60):
        return self.session.get(f"{self.base_url}{path}", params=params, timeout=timeout)

    # ------------------ Diagnostics -------------------
    def diag_core(self) -> Tuple[int, str]:
        r = self._get("/rest/api/3/myself")
        return r.status_code, (r.text[:400] if r.text else "")

    def diag_jsm(self) -> Tuple[int, str]:
        r = self._get("/rest/servicedeskapi/servicedesk")
        return r.status_code, (r.text[:400] if r.text else "")

    # ------------------ Capability --------------------
    def can_use_core(self) -> bool:
        if self._core_ok is not None:
            return self._core_ok
        code, _ = self.diag_core()
        self._core_ok = (code == 200)
        return self._core_ok

    # ------------------ Core Search (CORRIGIDO) ------
    def _core_search_all(self, jql: str, fields=None, page_size: int = 100):
        """
        Usando o endpoint estável:
          POST /rest/api/3/search
          body: {"jql": "...", "startAt": N, "maxResults": K, "fields": [...]}
        """
        start_at = 0
        while True:
            payload = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": page_size
            }
            if fields is not None:
                payload["fields"] = fields

            r = self._post("/rest/api/3/search", payload)
            if r.status_code != 200:
                raise RuntimeError(f"Jira search error ({r.status_code}): {r.text}")

            data = r.json()
            issues = data.get("issues", []) or []
            total = int(data.get("total", 0) or 0)

            if not issues:
                return

            for it in issues:
                yield it

            start_at += len(issues)
            if start_at >= total:
                return

    # ------------------ JSM Search (fallback) ---------
    def _jsm_service_desk_id(self, project_key: str) -> str:
        r = self._get("/rest/servicedeskapi/servicedesk")
        if r.status_code != 200:
            raise RuntimeError(f"JSM servicedesk error ({r.status_code}): {r.text}")
        desks = r.json().get("values", []) or []
        for d in desks:
            if str(d.get("projectKey")).upper() == project_key.upper():
                return str(d.get("id"))
        raise RuntimeError(
            f"Service Desk do projeto '{project_key}' não encontrado. "
            f"Vistos: {[d.get('projectKey') for d in desks]}"
        )

    def _jsm_list_requests(self, service_desk_id: str, start: int, limit: int):
        params = {
            "serviceDeskId": service_desk_id,
            "requestStatus": "all",
            "start": start,
            "limit": limit,
            "expand": "requestFieldValues",
        }
        r = self._get("/rest/servicedeskapi/request", params=params)
        if r.status_code != 200:
            raise RuntimeError(f"JSM request list error ({r.status_code}): {r.text}")
        return r.json()

    @staticmethod
    def _flatten_jsm_fields(items: List[dict]) -> Dict[str, str]:
        out = {}
        for f in items or []:
            fid = f.get("fieldId") or f.get("name") or f.get("label") or "unknown"
            val = f.get("value")
            if isinstance(val, list):
                sval = ", ".join([str(v) for v in val])
            elif isinstance(val, dict):
                sval = val.get("name") or val.get("value") or str(val)
            else:
                sval = "" if val is None else str(val)
            out[fid] = sval
        return out

    # ------------------ Public API --------------------
    def search_all(self, project_key: str, jql: Optional[str], fields=None,
                   page_size: int = 100, force_core: bool = False):
        """
        Se force_core=True → usa apenas Core JQL.
        Caso contrário: tenta Core; se não puder, usa JSM (listar requests).
        """
        if force_core or self.can_use_core():
            if not jql:
                jql = f"project = {project_key} ORDER BY created DESC"
            yield from self._core_search_all(jql, fields=fields, page_size=page_size)
            return

        # Fallback JSM (exige conta com licença de agente JSM)
        sdid = self._jsm_service_desk_id(project_key)
        start = 0
        while True:
            data = self._jsm_list_requests(sdid, start, page_size)
            values = data.get("values", []) or []
            if not values:
                break
            for req in values:
                yield {
                    "key": req.get("issueIdOrKey"),
                    "fields": {
                        "summary": req.get("summary"),
                        "created": (req.get("createdDate") or {}).get("iso8601"),
                        **self._flatten_jsm_fields(req.get("requestFieldValues", [])),
                    },
                }
            start += len(values)
            if start >= int(data.get("size", start)):
                break

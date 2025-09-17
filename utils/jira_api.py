import base64
import requests
from typing import Iterable, Optional, List

class JiraClient:
    """
    Cliente simples (modelo antigo):
    - Autentica com Basic (email + API token)
    - Usa somente o endpoint estável: POST /rest/api/3/search
    - Faz paginação até trazer todos os issues do JQL
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

    def search_all(self, jql: str, fields: Optional[List[str]] = None,
                   page_size: int = 100) -> Iterable[dict]:
        """
        Itera por todos os issues que batem no JQL.
        Endpoint: POST /rest/api/3/search
        Body: {"jql": "...", "startAt": N, "maxResults": K, "fields": [...]}
        """
        start_at = 0
        while True:
            payload = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": page_size,
            }
            if fields is not None:
                payload["fields"] = fields

            r = self.session.post(f"{self.base_url}/rest/api/3/search", json=payload, timeout=60)
            if r.status_code != 200:
                # mantém o comportamento do app antigo: estoura com a mensagem bruta da API
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

    @staticmethod
    def pick_display(v):
        """Formata valores de campos de forma amigável (igual ao modelo antigo)."""
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

import requests, base64

class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        token = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Basic {token}",
        })

    def _post(self, path: str, payload: dict, timeout: int = 60):
        url = f"{self.base_url}{path}"
        return self.session.post(url, json=payload, timeout=timeout)

    def search_all(self, jql: str, fields=None, page_size: int = 100):
        """
        Itera sobre TODOS os resultados de um JQL.

        - Tenta primeiro o endpoint novo:   POST /rest/api/3/search/jql   (usa chave 'query')
        - Se der 404/410, faz fallback para POST /rest/api/3/search        (usa chave 'jql')
        """
        start_at = 0
        use_new = True  # tenta novo primeiro

        while True:
            if use_new:
                payload = {"query": jql, "maxResults": page_size, "startAt": start_at}
                if fields is not None:
                    payload["fields"] = fields
                path = "/rest/api/3/search/jql"
            else:
                payload = {"jql": jql, "maxResults": page_size, "startAt": start_at}
                if fields is not None:
                    payload["fields"] = fields
                path = "/rest/api/3/search"

            r = self._post(path, payload)

            # se a instância não suportar o novo, troca uma vez para o antigo
            if use_new and r.status_code in (404, 410):
                use_new = False
                continue

            if r.status_code != 200:
                try:
                    detail = r.text
                except Exception:
                    detail = f"HTTP {r.status_code}"
                raise RuntimeError(f"Jira search error ({r.status_code}): {detail}")

            data = r.json()
            issues = data.get("issues", [])
            if not issues:
                break

            for it in issues:
                yield it

            start_at += len(issues)
            if start_at >= data.get("total", start_at):
                break

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

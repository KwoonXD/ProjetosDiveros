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

    def search_all(self, jql: str, fields=None, page_size: int = 100):
        """Retorna todos os chamados de acordo com o JQL (paginado)."""
        start_at = 0
        while True:
            payload = {"jql": jql, "maxResults": page_size, "startAt": start_at}
            if fields is not None:
                payload["fields"] = fields
            url = f"{self.base_url}/rest/api/3/search"
            r = self.session.post(url, json=payload, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"Jira search error ({r.status_code}): {r.text}")
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

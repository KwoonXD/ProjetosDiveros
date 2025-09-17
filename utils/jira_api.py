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
        Novo formato obrigatório: POST /rest/api/3/search/jql
        {
          "queries": [ { "jql": "...", "startAt": 0, "maxResults": 50, "fields": [...] } ]
        }
        """
        start_at = 0
        while True:
            query_obj = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": page_size,
            }
            if fields is not None:
                query_obj["fields"] = fields

            payload = {"queries": [query_obj]}
            r = self._post("/rest/api/3/search/jql", payload)

            if r.status_code != 200:
                raise RuntimeError(f"Jira search error ({r.status_code}): {r.text}")

            data = r.json()
            queries = data.get("queries", [])
            if not queries:
                break

            issues = queries[0].get("issues", [])
            if not issues:
                break

            for it in issues:
                yield it

            start_at += len(issues)
            if start_at >= queries[0].get("total", start_at):
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

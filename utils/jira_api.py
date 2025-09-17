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

    def _try_search_once(self, mode: int, jql: str, page_size: int, start_at: int, fields):
        """
        mode:
          1 -> POST /rest/api/3/search/jql  with {'jql': ...}
          2 -> POST /rest/api/3/search/jql  with {'query': ...}
          3 -> POST /rest/api/3/search      with {'jql': ...}
        """
        if mode == 1:
            path = "/rest/api/3/search/jql"
            payload = {"jql": jql, "maxResults": page_size, "startAt": start_at}
        elif mode == 2:
            path = "/rest/api/3/search/jql"
            payload = {"query": jql, "maxResults": page_size, "startAt": start_at}
        else:
            path = "/rest/api/3/search"
            payload = {"jql": jql, "maxResults": page_size, "startAt": start_at}

        if fields is not None:
            payload["fields"] = fields

        resp = self._post(path, payload)
        ok = (resp.status_code == 200)
        return ok, resp

    def search_all(self, jql: str, fields=None, page_size: int = 100):
        """
        Itera todos os resultados de um JQL. Para cada página tenta:
          1) /search/jql com 'jql'
          2) /search/jql com 'query'
          3) /search com 'jql'
        Progride com o primeiro que retornar 200. Se todos falharem, levanta erro.
        """
        start_at = 0
        working_mode = None  # trava o modo que funcionou para as próximas páginas

        while True:
            modes = [working_mode] if working_mode else [1, 2, 3]
            last_resp = None
            success = False

            for mode in modes:
                if mode is None:
                    continue
                ok, resp = self._try_search_once(mode, jql, page_size, start_at, fields)
                last_resp = resp
                if ok:
                    success = True
                    working_mode = mode  # fixar para as próximas páginas
                    data = resp.json()
                    break

            if not success:
                # tenta os demais modos (se ainda não tentou)
                for mode in [m for m in [1,2,3] if m not in modes]:
                    ok, resp = self._try_search_once(mode, jql, page_size, start_at, fields)
                    last_resp = resp
                    if ok:
                        success = True
                        working_mode = mode
                        data = resp.json()
                        break

            if not success:
                detail = last_resp.text if last_resp is not None else "no response"
                code = last_resp.status_code if last_resp is not None else "?"
                raise RuntimeError(f"Jira search error ({code}): {detail}")

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

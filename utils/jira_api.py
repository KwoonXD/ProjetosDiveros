import requests, base64, urllib.parse as _url

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

    # ---------- HTTP helpers ----------
    def _post(self, path: str, payload: dict, timeout: int = 60):
        return self.session.post(f"{self.base_url}{path}", json=payload, timeout=timeout)

    def _get(self, path: str, params: dict, timeout: int = 60):
        return self.session.get(f"{self.base_url}{path}", params=params, timeout=timeout)

    # ---------- Universal search (handles new & old APIs) ----------
    def _try_page(self, mode: int, jql: str, start_at: int, page_size: int, fields):
        """
        mode:
          1 -> POST /rest/api/3/search/jql  body: {'queries':[{'jql', 'startAt','maxResults','fields'}]}
          2 -> POST /rest/api/3/search/jql  body: {'jql', 'startAt','maxResults','fields'}
          3 -> GET  /rest/api/3/search/jql  params: jql, startAt, maxResults, fields
          4 -> POST /rest/api/3/search      body: {'jql','startAt','maxResults','fields'}
        Returns: (ok:bool, resp, issues:list, total:int)
        """
        fields_list = fields if isinstance(fields, list) else None

        if mode == 1:
            q = {"jql": jql, "startAt": start_at, "maxResults": page_size}
            if fields_list is not None:
                q["fields"] = fields_list
            resp = self._post("/rest/api/3/search/jql", {"queries": [q]})
            if resp.status_code == 200:
                data = resp.json()
                queries = data.get("queries") or []
                if not queries:
                    return True, resp, [], 0
                part = queries[0]
                return True, resp, part.get("issues", []) or [], int(part.get("total", 0) or 0)
            return False, resp, None, None

        if mode == 2:
            body = {"jql": jql, "startAt": start_at, "maxResults": page_size}
            if fields_list is not None:
                body["fields"] = fields_list
            resp = self._post("/rest/api/3/search/jql", body)
            if resp.status_code == 200:
                data = resp.json()
                return True, resp, data.get("issues", []) or [], int(data.get("total", 0) or 0)
            return False, resp, None, None

        if mode == 3:
            params = {"jql": jql, "startAt": start_at, "maxResults": page_size}
            if fields_list is not None:
                # API aceita fields separados por vírgula
                params["fields"] = ",".join(fields_list)
            resp = self._get("/rest/api/3/search/jql", params)
            if resp.status_code == 200:
                data = resp.json()
                return True, resp, data.get("issues", []) or [], int(data.get("total", 0) or 0)
            return False, resp, None, None

        # mode 4: legacy fallback
        body = {"jql": jql, "startAt": start_at, "maxResults": page_size}
        if fields_list is not None:
            body["fields"] = fields_list
        resp = self._post("/rest/api/3/search", body)
        if resp.status_code == 200:
            data = resp.json()
            return True, resp, data.get("issues", []) or [], int(data.get("total", 0) or 0)
        return False, resp, None, None

    def search_all(self, jql: str, fields=None, page_size: int = 100):
        """
        Itera todos os issues do JQL. Tenta na ordem: modos 1→2→3→4.
        Após o primeiro sucesso, fixa o modo nas próximas páginas.
        """
        start_at = 0
        working_mode = None
        last_resp = None

        while True:
            modes = [working_mode] if working_mode else [1, 2, 3, 4]
            ok = False
            issues = []
            total = 0

            for mode in modes:
                if mode is None:
                    continue
                ok, resp, issues, total = self._try_page(mode, jql, start_at, page_size, fields)
                last_resp = resp
                if ok:
                    working_mode = mode
                    break

            if not ok:
                detail = last_resp.text if last_resp is not None else "no response"
                code = last_resp.status_code if last_resp is not None else "?"
                raise RuntimeError(f"Jira search error ({code}): {detail}")

            if not issues:
                break

            for it in issues:
                yield it

            start_at += len(issues)
            if start_at >= (total or start_at):
                break

    # ---------- Dump fields for a known issue key ----------
    def dump_fields(self, issue_key: str):
        """
        Retorna tupla (report_text:str, raw_issue:dict).
        report_text lista 'id | name | short' para facilitar montar o fieldmap.
        """
        url = f"{self.base_url}/rest/api/3/issue/{_url.quote(issue_key)}"
        # expand=names devolve mapeamento id->nome amigável
        resp = self.session.get(url, params={"expand": "names"}, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"Jira issue error ({resp.status_code}): {resp.text}")
        issue = resp.json()
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

import base64
import requests
from typing import Dict, List, Optional, Tuple

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
        self._core_cache: Optional[bool] = None

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
        if self._core_cache is not None:
            return self._core_cache
        code, _ = self.diag_core()
        self._core_ca

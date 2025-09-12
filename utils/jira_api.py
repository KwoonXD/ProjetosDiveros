# utils/jira_api.py
import os
import requests
import math
import streamlit as st

def _base_info():
    cfg = st.secrets["JIRA"]
    email = cfg["EMAIL"]
    token = cfg["API_TOKEN"]
    cloud_id = cfg.get("CLOUD_ID", "")
    use_ex_api = bool(cfg.get("USE_EX_API", True))
    subdomain = cfg.get("SITE_SUBDOMAIN", "")
    timeout = int(cfg.get("TIMEOUT_SECS", 30))
    page_size = int(cfg.get("PAGE_SIZE", 100))
    return email, token, cloud_id, use_ex_api, subdomain, timeout, page_size

def _base_url():
    _, _, cloud_id, use_ex_api, subdomain, _, _ = _base_info()
    if use_ex_api:
        return f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"
    else:
        return f"https://{subdomain}.atlassian.net/rest/api/3"

def jql_search(jql: str):
    email, token, _, _, _, timeout, page_size = _base_info()
    base = _base_url()
    auth = (email, token)

    issues = []
    start_at = 0

    while True:
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": page_size
        }
        resp = requests.get(f"{base}/search", params=params, auth=auth, timeout=timeout)
        if not resp.ok:
            raise RuntimeError(f"Jira search error ({resp.status_code}): {resp.text}")

        data = resp.json()
        issues.extend(data.get("issues", []))

        total = data.get("total", 0)
        start_at += page_size
        if start_at >= total:
            break

    return issues

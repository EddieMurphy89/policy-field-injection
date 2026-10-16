"""Minimal OpenRouter client for TypeSafe Jev (System One decision model).

Reads the API key from the OPENROUTER_API_KEY environment variable.
"""

import json
import os
import time

import requests

API_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = os.environ.get("JEV_MODEL", "~typesafe/jev-latest")


class JevError(RuntimeError):
    pass


def ask(state, questions, model=MODEL, timeout=30, retries=5):
    """Send one decision request. Returns the full decoded JSON response.

    带指数退避重试: 并发压测时代理/网关偶发连接重置与限流。"""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise JevError("OPENROUTER_API_KEY is not set")
    if isinstance(state, (dict, list)):
        state_payload = state
    else:
        state_payload = str(state)
    body = json.dumps({"model": model, "state": state_payload, "questions": questions})
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.post(API_URL, headers=headers, data=body, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                last_err = JevError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            else:
                raise JevError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
        time.sleep(min(2 ** attempt, 10))
    raise JevError(f"request failed after {retries} attempts: {last_err}")


def answers_of(response):
    return response["answers"]


def cost_of(response):
    return response.get("usage", {}).get("cost")

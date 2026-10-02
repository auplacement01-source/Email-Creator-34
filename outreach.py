from __future__ import annotations

import os
import html
import json
import re
from typing import Any
from urllib.parse import urlparse
import requests
import streamlit as st

FACULTIES = [
    "Faculty of AUSOM",
    "Faculty of Social Sciences",
    "Faculty of Aerospace and Strategic Studies",
]

FIT_TERMS = {
    "Faculty of AUSOM": ["business", "bank", "finance", "account", "marketing", "management", "retail", "e-commerce", "supply chain", "logistics", "consulting", "fmcg", "sales", "human resources", "hr", "economics", "insurance", "audit", "commerce"],
    "Faculty of Social Sciences": ["social", "education", "university", "school", "ngo", "media", "communication", "psychology", "policy", "research", "government", "development", "public", "training", "journalism", "humanitarian", "think tank", "culture"],
    "Faculty of Aerospace and Strategic Studies": ["aerospace", "aviation", "airline", "defence", "defense", "strategic", "security", "military", "space", "aircraft", "drone", "cybersecurity", "cyber", "satellite", "engineering", "nuclear", "intelligence"],
}


def faculty_fit(industry: str = "", company: str = "", position: str = "") -> tuple[list[str], str]:
    text = f"{industry} {company} {position}".lower()
    scores = {faculty: sum(1 for term in terms if term in text) for faculty, terms in FIT_TERMS.items()}
    matched = [faculty for faculty, score in scores.items() if score > 0]
    if not matched:
        matched = list(FACULTIES)
        note = "No clear keyword match; review all three faculty options manually."
    else:
        note = "Suggested from organization/industry keywords only; confirm actual student fit before outreach."
    return matched, note


def _get_secret(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value: return str(value)
    try: return str(st.secrets.get(name, default))
    except Exception: return default


def create_email(company: str, first_name: str, industry: str, faculties: list[str], extra_context: str = "") -> tuple[str, str, str]:
    key = _get_secret("GROQ_API_KEY")
    model = _get_secret("GROQ_MODEL", "openai/gpt-oss-20b")
    faculty_line = ", ".join(faculties) if faculties else "Air University H-11 Campus"
    if key:
        try:
            prompt = (
                "Write a concise, courteous employer outreach email asking whether the organization may consider summer 2027 internship opportunities for students at Air University H-11 Campus. "
                "Use only the facts provided. Do not invent student skills, prior relationships, numbers, endorsements, or employer programs. Avoid pressure and avoid claiming a partnership. "
                "Mention the selected faculty/program areas exactly. Keep the body around 100-140 words. Return exactly two labeled sections: SUBJECT: (one line), then BODY: (the email body).\n\n"
                f"Organization: {company}\nIndustry: {industry or 'not specified'}\nRecipient greeting name: {first_name or 'there'}\nProgram areas: {faculty_line}\nContext: {extra_context or 'none'}"
            )
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json={"model":model,"temperature":0.35,"messages":[{"role":"system","content":"You write accurate, respectful university internship outreach. Never make up facts."},{"role":"user","content":prompt}]},timeout=30)
            response.raise_for_status()
            content=response.json()["choices"][0]["message"]["content"] or ""
            parsed=re.search(r"(?is)^\s*SUBJECT:\s*(.*?)\s*BODY:\s*(.*)$",content)
            if not parsed: raise ValueError("The model did not return the required subject/body labels.")
            return parsed.group(1).strip(), parsed.group(2).strip(), f"Groq · {model}"
        except Exception as exc:
            st.warning(f"Groq drafting was unavailable; using the transparent template instead ({exc}).")
    greeting = f"Dear {first_name}," if first_name and first_name.lower() != "there" else "Dear Internship/HR Team,"
    subject = "Summer 2027 internship opportunities for Air University students"
    body = (
        f"{greeting}\n\n"
        f"I am reaching out on behalf of Air University’s H-11 Campus to ask whether {company} may be open to considering summer 2027 internship opportunities for our students. Based on the organization’s field, relevant areas may include {faculty_line}. These are suggested areas for discussion, not assumptions about specific student qualifications.\n\n"
        "If your team expects to host interns, could you share the functions, application process, expected timeline, and any eligibility requirements? We would be glad to coordinate suitable student profiles through the appropriate university channel.\n\n"
        "Thank you for considering the request."
    )
    return subject, body, "Local template"


def search_organizations(query: str, max_results: int = 8) -> list[dict[str, str]]:
    key=_get_secret("GROQ_API_KEY")
    if not key:
        raise RuntimeError("Set GROQ_API_KEY in Streamlit secrets to enable in-app web search; without it, use the direct search links on this page.")
    prompt=(
        f"Search the web for up to {max_results} real organizations relevant to this query: {query!r}. "
        "Return only JSON with a top-level results array; each item must contain title, url, and snippet. "
        "Use publicly accessible source URLs as absolute https URLs. Do not include or infer email addresses, personal contact details, or phone numbers. "
        "Do not invent organizations or source URLs. Prefer official organization websites where available, otherwise provide the exact source page and mark the snippet as unverified."
    )
    response=requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
        json={"model":"openai/gpt-oss-20b","messages":[{"role":"user","content":prompt}],"temperature":1,"top_p":1,"max_completion_tokens":2048,"stream":False,"reasoning_effort":"low","tool_choice":"required","tools":[{"type":"browser_search"}]},
        timeout=90,
    )
    response.raise_for_status()
    content=response.json()["choices"][0]["message"].get("content") or ""
    match=re.search(r"\{.*\}",content,re.S)
    if not match:
        raise RuntimeError("Web search returned no parseable organization list. Try again or open the direct browser-search link.")
    data=json.loads(match.group(0))
    cleaned=[]
    for item in data.get("results",[]) if isinstance(data,dict) else []:
        title=str(item.get("title") or "").strip()
        url=str(item.get("url") or "").strip()
        parsed=urlparse(url)
        if not title or parsed.scheme not in ("http","https") or not parsed.netloc:
            continue
        cleaned.append({"title":title[:200],"url":url,"snippet":str(item.get("snippet") or "")[:1000]})
    if not cleaned:
        raise RuntimeError("Web search did not return source URLs that could be checked. Try a broader query.")
    return cleaned[:max_results]


@st.cache_resource(show_spinner=False)
def _msal_app(client_id: str, authority: str):
    import msal
    return msal.PublicClientApplication(client_id, authority=authority)


def start_outlook_device_flow(tenant_id: str = "common") -> dict[str, Any]:
    client_id=_get_secret("MICROSOFT_CLIENT_ID")
    if not client_id:
        raise RuntimeError("Set MICROSOFT_CLIENT_ID in Streamlit secrets after registering a public-client app in Microsoft Entra.")
    authority=f"https://login.microsoftonline.com/{tenant_id or 'common'}"
    app=_msal_app(client_id,authority)
    flow=app.initiate_device_flow(scopes=["User.Read","Mail.Send"])
    if "user_code" not in flow:
        raise RuntimeError(str(flow.get("error_description") or flow))
    st.session_state["outlook_device_flow"]=flow
    return flow


def finish_outlook_device_flow(tenant_id: str = "common") -> dict[str, Any]:
    flow=st.session_state.get("outlook_device_flow")
    if not flow:
        raise RuntimeError("Start Outlook sign-in first.")
    client_id=_get_secret("MICROSOFT_CLIENT_ID")
    authority=f"https://login.microsoftonline.com/{tenant_id or 'common'}"
    result=_msal_app(client_id,authority).acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(str(result.get("error_description") or result.get("error") or result))
    st.session_state["graph_access_token"]=result["access_token"]
    st.session_state["outlook_account"]=result.get("id_token_claims",{}).get("preferred_username") or result.get("id_token_claims",{}).get("email") or "Signed-in Outlook account"
    st.session_state.pop("outlook_device_flow",None)
    return result


def send_graph_email(to_email: str, subject: str, body_text: str, signature: str = "") -> dict[str, Any]:
    token=st.session_state.get("graph_access_token")
    if not token:
        raise RuntimeError("Sign in to Outlook before sending.")
    full_body=body_text.strip()
    if signature.strip(): full_body += "\n\n" + signature.strip()
    payload={"message":{"subject":subject,"body":{"contentType":"HTML","content":"<div style=\"font-family:Arial,sans-serif;white-space:pre-wrap\">"+html.escape(full_body).replace("\n","<br>")+"</div>"},"toRecipients":[{"emailAddress":{"address":to_email}}]},"saveToSentItems":True}
    response=requests.post("https://graph.microsoft.com/v1.0/me/sendMail",headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},json=payload,timeout=30)
    if response.status_code not in (200,202):
        raise RuntimeError(f"Microsoft Graph returned {response.status_code}: {response.text[:1000]}")
    return {"status_code":response.status_code,"request_id":response.headers.get("request-id")}

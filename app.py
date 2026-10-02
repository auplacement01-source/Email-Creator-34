from __future__ import annotations

import os
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

from storage import Repository
from outreach import FACULTIES, faculty_fit, create_email, search_organizations
from word_export import build_daily_pack

st.set_page_config(page_title="AU Internship Outreach", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
:root { --ink:#11243a; --muted:#718095; --paper:#f4f6f8; --blue:#1468a0; --navy:#10253d; --line:#e3e8ed; }
html,body,[class*="css"] { font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }
.stApp { background:var(--paper); color:var(--ink); }
.block-container { padding-top:1.6rem; max-width:1420px; }
[data-testid="stSidebar"] { background:#10253d; border-right:1px solid #233b54; }
[data-testid="stSidebar"] * { color:#eaf1f6 !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { padding:.46rem .55rem; border-radius:9px; }
[data-testid="stMetric"] { background:#fff; border:1px solid var(--line); padding:16px 18px; border-radius:14px; box-shadow:0 3px 12px rgba(17,36,58,.035); }
[data-testid="stMetricLabel"] { color:#718095; font-weight:600; }
[data-testid="stMetricValue"] { color:#11243a; }
section[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px; }
hr { border-color:var(--line); }
h1,h2,h3 { letter-spacing:-.035em; }
h1 { font-family:Georgia,"Times New Roman",serif !important; font-size:2.55rem !important; font-weight:600 !important; }
h2 { font-family:Georgia,"Times New Roman",serif !important; font-size:1.8rem !important; }
[data-testid="stButton"] button[kind="primary"] { background:#1468a0; border:0; border-radius:10px; min-height:44px; font-weight:700; }
[data-testid="stButton"] button { border-radius:10px; min-height:40px; }
[data-testid="stAlert"] { border-radius:12px; }
.au-brand { display:flex; gap:12px; align-items:center; padding:14px 4px 26px; }
.au-mark { width:42px;height:42px;border-radius:12px;background:#1468a0;color:white;display:grid;place-items:center;font-weight:800;position:relative;box-shadow:0 7px 18px #0d192b66; }
.au-mark:after { content:'';position:absolute;left:7px;right:7px;bottom:7px;height:8px;border-top:1px solid #93c6e2;transform:skewY(-13deg); }
.au-name { font-size:13px;font-weight:700;line-height:1.3;letter-spacing:.01em; }
.au-sub { font-size:10px;opacity:.67;letter-spacing:.08em;text-transform:uppercase; }
.eyebrow { color:#1468a0; font-size:.72rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;margin-bottom:.35rem; }
.lead { color:#65758b;font-size:1.02rem;max-width:800px;margin-top:-.4rem; }
.small-note { color:#758397;font-size:.82rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def secret(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return str(value)
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def local_today() -> date:
    return datetime.now(ZoneInfo("Asia/Karachi")).date()


def draft_local_day(draft: dict) -> date | None:
    stamp = draft.get("created_at")
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
        return parsed.astimezone(ZoneInfo("Asia/Karachi")).date()
    except (TypeError, ValueError):
        return None


def valid_email(value: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", value.strip()))


def require_login() -> bool:
    password = secret("APP_PASSWORD")
    if not password:
        st.session_state["au_demo_mode"] = True
        return True
    st.session_state["au_demo_mode"] = False
    if not st.session_state.get("au_authenticated"):
        st.markdown('<div class="eyebrow">AIR UNIVERSITY · H-11 CAMPUS</div><h1>Internship outreach desk</h1>', unsafe_allow_html=True)
        st.markdown('<p class="lead">A reviewed, auditable workspace for preparing daily internship outreach packs.</p>', unsafe_allow_html=True)
        with st.form("login_form"):
            entered = st.text_input("Workspace password", type="password")
            submit = st.form_submit_button("Unlock workspace", type="primary")
            if submit:
                import hmac
                if hmac.compare_digest(entered, password):
                    st.session_state["au_authenticated"] = True
                    st.rerun()
                else:
                    st.error("That password did not match.")
        st.caption("Set APP_PASSWORD in Streamlit secrets before using real employer data.")
        return False
    return True


if not require_login():
    st.stop()

repo = Repository()
if st.session_state.get("au_demo_mode") and not repo.list_employers():
    demo_rows = [
        {"company_name": "Northstar Analytics (Demo)", "email": "people@example.org", "industry": "AI, Data and Robotics", "country": "Pakistan", "source": "synthetic demo", "status": "new"},
        {"company_name": "Civic Futures Lab (Demo)", "email": "internships@example.org", "industry": "Public Policy and Research", "country": "Pakistan", "source": "synthetic demo", "status": "new"},
        {"company_name": "Aero Systems Group (Demo)", "email": "careers@example.org", "industry": "Aerospace and Defence", "country": "Pakistan", "source": "synthetic demo", "status": "new"},
    ]
    for row in demo_rows:
        row["program_fit"], row["fit_notes"] = faculty_fit(row.get("industry", ""), row["company_name"])
    repo.upsert_employers(demo_rows)

st.sidebar.markdown('<div class="au-brand"><div class="au-mark">AU</div><div><div class="au-name">INTERNSHIP DESK</div><div class="au-sub">H-11 Campus · Summer 2027</div></div></div>', unsafe_allow_html=True)
page = st.sidebar.radio("WORKSPACE", ["Overview", "Employers", "Find organizations", "Daily email pack", "Draft review", "Activity log", "Settings"], label_visibility="visible")
st.sidebar.divider()
st.sidebar.caption(f"Data store · {repo.backend}")
if st.session_state.get("au_demo_mode"):
    st.sidebar.caption("Synthetic preview only. Real employer data is locked.")
elif st.sidebar.button("Lock workspace"):
    st.session_state.pop("au_authenticated", None)
    st.rerun()

employers = repo.list_employers()
drafts = repo.list_drafts()
by_id = {str(row["id"]): row for row in employers}


def daily_draft_count(day: date) -> int:
    """Use the database counter when available; fall back for an older deployed storage.py."""
    counter = getattr(repo, "daily_draft_count", None)
    if callable(counter):
        return int(counter(day))
    return sum(1 for draft in drafts if draft.get("status") != "discarded" and draft_local_day(draft) == day)


def page_header(kicker: str, title: str, desc: str):
    st.markdown(f'<div class="eyebrow">{kicker}</div><h1>{title}</h1><p class="lead">{desc}</p>', unsafe_allow_html=True)


def display_fit(items):
    return ", ".join(items or []) or "Review manually"


if page == "Overview":
    page_header("OUTREACH OPERATIONS · SUMMER 2027", "Prepare a careful first hello.", "Create a small, reviewed daily pack, then copy and send each message yourself from your own email account.")
    today = local_today()
    start_raw = repo.get_setting("start_date", "2027-02-01")
    start_date = date.fromisoformat(start_raw) if isinstance(start_raw, str) else date(2027, 2, 1)
    cap = int(repo.get_setting("daily_cap", 5))
    prepared_today = daily_draft_count(today)
    pending = sum(d.get("status") == "draft" for d in drafts)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Employer records", len(employers))
    m2.metric("Drafts to review", pending)
    m3.metric("Prepared today", f"{prepared_today} / {cap}")
    m4.metric("Campaign opens", start_date.strftime("%b %Y"))
    left, right = st.columns([1.35, .85], gap="large")
    with left:
        st.subheader("Today's workflow")
        with st.container(border=True):
            st.markdown("**01 · Select verified employers**")
            st.caption("Import your workbook or review additional organization prospects and contacts.")
            st.markdown("**02 · Generate and review drafts**")
            st.caption("Edit the recipient, subject, and body; mark each draft reviewed before export.")
            st.markdown("**03 · Download one Word pack**")
            st.caption("Copy and send messages yourself. This app never connects to an email account.")
        st.markdown('<p class="small-note">Daily cap controls draft preparation. Manual sending and delivery are outside the app.</p>', unsafe_allow_html=True)
    with right:
        st.subheader("Campaign status")
        if today < start_date:
            st.warning(f"Daily campaign preparation opens {start_date.strftime('%d %B %Y')}.")
        elif prepared_today >= cap:
            st.warning("Today's draft cap has been reached.")
        else:
            st.success(f"{cap - prepared_today} draft slot(s) remain today.")
        if not secret("SUPABASE_URL") or not secret("SUPABASE_SERVICE_ROLE_KEY"):
            st.info("SQLite is preview-only. Configure Supabase before importing real employer data.")
        st.info("There is no Outlook integration or email-sending feature in this app.")
    st.subheader("Suggested faculty focus")
    fit_cols = st.columns(3)
    blurbs = ["Business, management, finance, marketing, operations and related placements.", "Policy, education, research, media, communication and community-facing roles.", "Aerospace, aviation, security, defence, space and strategic-studies environments."]
    for col, name, blurb in zip(fit_cols, FACULTIES, blurbs):
        with col, st.container(border=True):
            st.markdown(f"**{name}**")
            st.caption(blurb)

elif page == "Employers":
    page_header("LEAD MANAGEMENT · STEP 01", "Employer directory", "Import employer contacts, review contact quality, and suppress organizations that should not be contacted.")
    if st.session_state.get("au_demo_mode"):
        st.info("This preview is read-only and contains synthetic demo records. Add APP_PASSWORD and Supabase secrets to enable real-data intake.")
    elif not repo.supabase:
        st.warning("Real-data import is locked until Supabase is configured. Local SQLite is preview-only and may be ephemeral.")
    else:
        upload = st.file_uploader("Upload employer sheet (Excel or CSV)", type=["xlsx", "xls", "csv"], help="The workbook is read by this Streamlit server and is not added to the source repository.")
        if upload:
            try:
                frame = pd.read_csv(upload) if upload.name.lower().endswith(".csv") else pd.read_excel(upload)
                st.caption(f"Preview · {len(frame):,} rows · {len(frame.columns)} columns")
                st.dataframe(frame.head(12), use_container_width=True, hide_index=True)
                if st.button(f"Import {len(frame):,} rows", type="primary", key="import_sheet"):
                    imported, skipped = [], 0
                    for _, row in frame.iterrows():
                        raw = {str(key).strip().lower(): (None if pd.isna(value) else str(value).strip()) for key, value in row.to_dict().items()}
                        def pick(*keys):
                            return next((value for key, value in raw.items() if any(token in key for token in keys) and value), None)
                        email = pick("email")
                        company = pick("company name", "company", "organization", "organisation")
                        if not email or not valid_email(email) or not company:
                            skipped += 1
                            continue
                        industry = pick("industry", "sector") or ""
                        position = pick("position", "job title", "role") or ""
                        fits, note = faculty_fit(industry, company, position)
                        imported.append({"source": pick("source") or upload.name, "title": pick("title"), "first_name": pick("first name", "firstname", "given name"), "last_name": pick("last name", "lastname", "surname"), "position": position, "industry": industry, "company_name": company, "country": pick("country", "territory"), "email": email, "phone": pick("phone", "mobile"), "program_fit": fits, "fit_notes": note, "status": "new"})
                    added, updated = repo.upsert_employers(imported)
                    repo.log("employer_import", {"file": upload.name, "processed": len(imported), "added": added, "updated": updated, "skipped": skipped})
                    st.success(f"Import complete · {added} new · {updated} updated · {skipped} skipped for missing/invalid company or email.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Could not read/import this workbook: {exc}")
    st.divider()
    search = st.text_input("Search by company, industry, email, or contact", placeholder="Start typing a company or industry…")
    filtered = employers
    if search:
        term = search.lower()
        filtered = [row for row in employers if term in " ".join(str(row.get(key) or "") for key in ("company_name", "industry", "email", "first_name", "last_name")).lower()]
    view = [{"Company": row.get("company_name"), "Contact": (" ".join(value for value in [row.get("first_name"), row.get("last_name")] if value) or "—"), "Email": row.get("email") or "—", "Industry": row.get("industry") or "—", "Suggested faculty": display_fit(row.get("program_fit")), "Status": row.get("status", "new")} for row in filtered]
    st.dataframe(pd.DataFrame(view), use_container_width=True, hide_index=True, height=420)
    st.caption(f"Showing {len(filtered)} of {len(employers)} records. Do-not-contact and already-sent contacts are excluded from new draft generation.")
    choices = [row for row in employers if row.get("status") != "do_not_contact"]
    if choices and not st.session_state.get("au_demo_mode") and repo.supabase:
        selected_id = st.selectbox("Manage a contact", options=[str(row["id"]) for row in choices], format_func=lambda key: f"{by_id[key].get('company_name')} · {by_id[key].get('email') or 'no contact email'}")
        selected = by_id[selected_id]
        c1, c2 = st.columns(2)
        with c1:
            st.caption(f"Fit note: {selected.get('fit_notes') or 'Not assessed'}")
            if st.button("Mark do not contact", key="suppress_contact"):
                repo.update_employer(selected_id, {"status": "do_not_contact"})
                repo.log("contact_suppressed", {"company": selected.get("company_name")}, employer_id=selected_id)
                st.rerun()
        with c2:
            with st.form("verified_contact_form"):
                contact_email = st.text_input("Verified HR / internship email", value=selected.get("email") or "")
                contact_first = st.text_input("Contact first name", value=selected.get("first_name") or "")
                contact_last = st.text_input("Contact last name", value=selected.get("last_name") or "")
                contact_position = st.text_input("Contact position", value=selected.get("position") or "")
                save_contact = st.form_submit_button("Save verified contact")
            if save_contact:
                if contact_email.strip() and not valid_email(contact_email):
                    st.error("Enter a valid email or leave the field blank until verified.")
                else:
                    try:
                        normalized = contact_email.strip().lower() or None
                        same_recipient = normalized == ((selected.get("email") or "").strip().lower() or None)
                        next_status = selected.get("status", "prospect") if same_recipient and selected.get("status") in ("drafted", "sent", "do_not_contact") else ("new" if normalized else selected.get("status", "prospect"))
                        repo.update_employer(selected_id, {"email": normalized, "first_name": contact_first.strip(), "last_name": contact_last.strip(), "position": contact_position.strip(), "status": next_status})
                        repo.log("contact_verified", {"email": normalized, "contact_name": " ".join(value for value in [contact_first.strip(), contact_last.strip()] if value)}, employer_id=selected_id)
                        st.success("Verified contact saved. It can be selected in the Daily email pack workflow.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not save contact details: {exc}")

elif page == "Find organizations":
    page_header("PROSPECT DISCOVERY · STEP 02", "Find relevant organizations", "Search public web results by faculty and industry. Results are unverified; review the source before saving a prospect.")
    st.info("Discovery identifies organizations only. It does not scrape email addresses or contact anyone. With GROQ_API_KEY configured, the app uses Groq browser search and returns source links for human verification.")
    with st.form("search_form"):
        faculty = st.selectbox("Start from a faculty", FACULTIES)
        domain = st.text_input("Industry or employer type", placeholder="e.g., banks, policy think tanks, airlines, cybersecurity firms")
        country = st.text_input("Geography", value="Pakistan")
        limit = st.slider("Result count", 3, 12, 8)
        do_search = st.form_submit_button("Search public web", type="primary")
    if do_search:
        if not domain.strip():
            st.warning("Add an industry or employer type so results are relevant.")
        elif not secret("GROQ_API_KEY"):
            query = f"organizations {domain} internships careers {country}"
            st.warning("In-app web search needs a Groq API key. You can still open a browser search and add reviewed prospects manually.")
            st.link_button("Open Google search results", "https://www.google.com/search?q=" + quote_plus(query))
        else:
            query = f"organizations {domain} internships careers {country}"
            with st.spinner("Searching public organization results…"):
                try:
                    results = search_organizations(query, limit)
                    st.session_state["org_search_results"] = {"items": results, "faculty": faculty, "domain": domain, "query": query, "country": country}
                    repo.log("organization_search", {"query": query, "results": len(results)})
                except Exception as exc:
                    st.error(f"Search could not complete right now: {exc}. Try again later or add a known organization manually.")
    payload = st.session_state.get("org_search_results")
    if payload:
        items = payload.get("items", [])
        if not items:
            st.warning("No search results returned. Try a broader domain.")
        else:
            st.write(f"**{len(items)} results** · {payload.get('domain')} · {payload.get('faculty')}")
            for index, item in enumerate(items):
                with st.container(border=True):
                    left, right = st.columns([.82, .18])
                    with left:
                        st.markdown(f"**{item['title']}**")
                        st.caption(item.get("snippet") or "No description in result")
                        st.markdown(f"[Review source]({item['url']})")
                    with right:
                        if st.button("Save prospect", key=f"save_result_{index}", disabled=bool(st.session_state.get("au_demo_mode") or not repo.supabase)):
                            company = re.split(r"\s[|–—-]\s", item["title"])[0].strip()[:180]
                            row = {"company_name": company, "industry": payload.get("domain"), "website": item["url"], "source_url": item["url"], "source": "public web search · human-reviewed", "country": payload.get("country", "Pakistan"), "status": "prospect", "program_fit": [payload.get("faculty")], "fit_notes": "Unverified search result; verify the organization, source, and contact email before drafting."}
                            repo.upsert_employers([row])
                            repo.log("prospect_saved", {"company": company, "source_url": item["url"]})
                            st.success("Prospect saved without an email address.")
                            st.rerun()
    st.divider()
    with st.expander("Add a known organization manually"):
        if st.session_state.get("au_demo_mode"):
            st.caption("Manual entry is disabled in demo mode.")
        elif not repo.supabase:
            st.caption("Configure Supabase before saving durable prospect records.")
        else:
            with st.form("manual_prospect"):
                company = st.text_input("Organization name")
                website = st.text_input("Official website or source URL")
                industry = st.text_input("Industry")
                fit = st.multiselect("Possible faculty areas", FACULTIES)
                save = st.form_submit_button("Save as unverified prospect")
            if save and company.strip():
                fits = fit or faculty_fit(industry, company)[0]
                repo.upsert_employers([{"company_name": company.strip(), "website": website.strip() or None, "source_url": website.strip() or None, "industry": industry, "source": "manual prospect", "status": "prospect", "program_fit": fits, "fit_notes": "User-entered prospect; verify organization details and contact before drafting."}])
                repo.log("prospect_manual", {"company": company.strip()})
                st.success("Prospect saved.")
                st.rerun()

elif page == "Daily email pack":
    page_header("DAILY DRAFTING · STEP 03", "Build today's Word pack", "Prepare a capped set of editable messages, review them, and download one Word document for manual copy-and-send.")
    today = local_today()
    start_raw = repo.get_setting("start_date", "2027-02-01")
    start_date = date.fromisoformat(start_raw) if isinstance(start_raw, str) else date(2027, 2, 1)
    cap = int(repo.get_setting("daily_cap", 5))
    prepared = daily_draft_count(today)

    if st.session_state.get("au_demo_mode"):
        st.warning("Synthetic demonstration only. This sample uses example.org addresses and does not save drafts or contact anyone.")
        if st.button("Build sample Word pack", type="primary"):
            now = datetime.now(ZoneInfo("UTC")).isoformat()
            sample_drafts = []
            for employer in employers:
                fit = employer.get("program_fit") or FACULTIES
                subject = "Summer 2027 internship opportunities for Air University students"
                body = (
                    "Dear Internship Team,\n\n"
                    f"Air University H-11 Campus is exploring summer 2027 internship opportunities with organizations such as {employer.get('company_name', 'this demo organization')}. "
                    f"Potential areas may include {', '.join(fit)}. These are discussion areas only, not assumptions about student qualifications.\n\n"
                    "Could you share any relevant functions, eligibility requirements, timelines, and application process?\n\n"
                    "Thank you for your consideration."
                )
                sample_drafts.append({"id": f"sample-{employer['id']}", "employer_id": employer["id"], "to_email": employer["email"], "subject": subject, "body_text": body, "program_fit": fit, "status": "draft", "approved_at": now, "created_at": now})
            if sample_drafts:
                st.session_state["sample_pack_bytes"] = build_daily_pack(sample_drafts, by_id, today)
                st.session_state["sample_pack_name"] = f"AU_Synthetic_Sample_Pack_{today.isoformat()}.docx"
                st.success(f"Created a sample Word pack with {len(sample_drafts)} synthetic messages.")
        if st.session_state.get("sample_pack_bytes"):
            st.download_button("Download synthetic sample Word pack", st.session_state["sample_pack_bytes"], file_name=st.session_state["sample_pack_name"], mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    elif not repo.supabase:
        st.error("Real draft preparation is disabled until Supabase is configured. No records can be written to preview-only SQLite.")
    else:
        metrics = st.columns(3)
        metrics[0].metric("Prepared today", f"{prepared} / {cap}")
        metrics[1].metric("Slots remaining", max(0, cap - prepared))
        metrics[2].metric("Eligible verified contacts", sum(bool(row.get("email")) and row.get("status") not in ("do_not_contact", "drafted", "sent") for row in employers))
        if today < start_date:
            st.warning(f"Draft generation opens on {start_date.strftime('%d %B %Y')}. You can import and review employer records before then.")
        remaining = max(0, cap - prepared)
        eligible = [row for row in employers if row.get("email") and row.get("status") not in ("do_not_contact", "drafted", "sent")]
        labels = {str(row["id"]): f"{row.get('company_name')} · {row.get('email')}" for row in eligible}
        selected_ids = st.multiselect("Select verified employers for today's batch", options=list(labels), format_func=lambda key: labels[key], help="Only verified contacts are shown. Each selected company receives one editable draft.")
        blocked = today < start_date or remaining <= 0 or not eligible
        if st.button("Generate selected drafts", type="primary", disabled=blocked or not selected_ids):
            if len(selected_ids) > remaining:
                st.error(f"The daily limit leaves room for {remaining} more draft(s), but {len(selected_ids)} were selected.")
            else:
                created = 0
                for employer_id in selected_ids:
                    employer = by_id[employer_id]
                    fits = employer.get("program_fit") or FACULTIES
                    subject, body, model = create_email(employer.get("company_name", ""), employer.get("first_name", ""), employer.get("industry", ""), fits, employer.get("fit_notes", ""))
                    draft = repo.create_draft({"employer_id": employer_id, "to_email": employer["email"], "subject": subject, "body_text": body, "program_fit": fits})
                    repo.update_employer(employer_id, {"status": "drafted"})
                    repo.log("draft_created", {"model": model, "subject": subject}, employer_id=employer_id, draft_id=draft["id"])
                    created += 1
                st.success(f"Created {created} draft(s). Review each one before Word export.")
                st.rerun()
        st.divider()
        st.markdown("### Download a daily Word pack")
        pack_day = st.date_input("Pack date (Asia/Karachi)", value=today, max_value=today, key="pack_date")
        day_drafts = [draft for draft in drafts if draft_local_day(draft) == pack_day and draft.get("status") != "discarded"]
        reviewed = [draft for draft in day_drafts if draft.get("approved_at") and draft.get("status") in ("draft", "sent")]
        unreviewed = len(day_drafts) - len(reviewed)
        if day_drafts:
            st.caption(f"{len(reviewed)} reviewed and ready for the Word pack · {unreviewed} not yet reviewed · {pack_day.strftime('%d %B %Y')}")
            table = []
            for draft in day_drafts:
                employer = by_id.get(str(draft.get("employer_id")), {})
                table.append({"Organization": employer.get("company_name", "—"), "To": draft.get("to_email"), "Subject": draft.get("subject"), "Review": "Reviewed" if draft.get("approved_at") else "Review needed", "Record": "Manually sent" if draft.get("status") == "sent" else draft.get("status")})
            st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
        if reviewed:
            pack_bytes = build_daily_pack(reviewed, by_id, pack_day)
            st.download_button("Download reviewed emails as Word", pack_bytes, file_name=f"AU_Summer_2027_Email_Pack_{pack_day.isoformat()}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", type="primary")
        elif day_drafts:
            st.info("Review the drafts first. Only messages marked reviewed are included in the Word download.")
        else:
            st.info("No drafts are recorded for this date yet.")
        st.caption("The Word file is generated in memory for download and is not saved in Git or sent from this app. Keep downloaded packs private.")

elif page == "Draft review":
    page_header("HUMAN REVIEW · STEP 04", "Review and edit drafts", "Inspect the exact recipient, subject, and body. Mark a message reviewed before it is included in a Word pack.")
    st.info("This app does not connect to Outlook or send messages. After downloading a reviewed pack, you copy each message into your own compose window and send it yourself.")
    queue = [draft for draft in drafts if draft.get("status") in ("draft", "send_error")]
    if not queue:
        st.info("No email drafts are waiting for review. Select verified contacts on the Daily email pack page.")
    else:
        ids = [str(draft["id"]) for draft in queue]
        selected_id = st.selectbox("Choose one draft", ids, format_func=lambda key: f"{by_id.get(str(next((d['employer_id'] for d in queue if str(d['id']) == key), '')), {}).get('company_name', 'Employer')} · {next((d.get('to_email', '') for d in queue if str(d['id']) == key), '')}")
        draft = next(row for row in queue if str(row["id"]) == selected_id)
        employer_id = str(draft.get("employer_id"))
        employer = by_id.get(employer_id, {})
        st.markdown(f"#### {employer.get('company_name', 'Employer')}")
        st.caption(f"Suggested faculty fit: {display_fit(draft.get('program_fit'))} · Draft date: {draft_local_day(draft) or 'unknown'}")
        with st.form("review_email_form"):
            recipient = st.text_input("Recipient email", value=draft.get("to_email", ""))
            subject = st.text_input("Subject", value=draft.get("subject", ""))
            body = st.text_area("Email body", value=draft.get("body_text", ""), height=300)
            save_edits = st.form_submit_button("Save edits")
            mark_reviewed = st.form_submit_button("Mark reviewed for Word pack", type="primary")
        if save_edits or mark_reviewed:
            if not valid_email(recipient):
                st.error("Enter a valid recipient email.")
            elif not subject.strip() or not body.strip():
                st.error("Subject and message body are required.")
            else:
                changes = {"to_email": recipient.strip().lower(), "subject": subject.strip(), "body_text": body.strip(), "status": "draft"}
                if mark_reviewed:
                    changes.update({"approved_by": "operator", "approved_at": datetime.now(ZoneInfo("UTC")).isoformat()})
                    event = "draft_reviewed"
                else:
                    changes.update({"approved_by": None, "approved_at": None})
                    event = "draft_edited"
                repo.update_draft(selected_id, changes)
                if recipient.strip().lower() != (employer.get("email") or "").strip().lower():
                    try:
                        repo.update_employer(employer_id, {"email": recipient.strip().lower()})
                    except Exception:
                        st.warning("The draft recipient was saved, but the employer directory already uses that email. Update the contact record separately if appropriate.")
                repo.log(event, {"recipient": recipient.strip().lower(), "subject": subject.strip()}, employer_id=employer_id, draft_id=selected_id)
                st.success("Draft marked reviewed and ready for the daily Word pack." if mark_reviewed else "Edits saved. Review confirmation was cleared; mark the draft reviewed after checking it again.")
                st.rerun()
        st.divider()
        sent_confirm = st.checkbox("I have already sent this exact message manually from my own email account.", key=f"manual_sent_confirm_{selected_id}")
        if st.button("Record my manual send", disabled=not sent_confirm or not draft.get("approved_at"), key=f"record_manual_send_{selected_id}"):
            sent_at = datetime.now(ZoneInfo("UTC")).isoformat()
            repo.update_draft(selected_id, {"status": "sent", "sent_at": sent_at})
            repo.update_employer(employer_id, {"status": "sent"})
            repo.log("email_marked_sent_manually", {"recipient": draft.get("to_email"), "subject": draft.get("subject"), "user_attested": True}, employer_id=employer_id, draft_id=selected_id)
            st.success("Your manual-send attestation was recorded. The app did not send or verify the email.")
            st.rerun()
        if not draft.get("approved_at"):
            st.caption("Mark this draft reviewed before recording a manual send.")
        st.caption("Your usual signature is not in the Word pack. Your own mail client may add its saved signature when you compose the message.")

elif page == "Activity log":
    page_header("AUDIT TRAIL · STEP 05", "Activity log", "A record of imports, prospect discovery, draft creation and edits, review, Word-pack preparation, and user-reported manual sends.")
    logs = repo.list_logs(500)
    if not logs:
        st.info("No activity recorded yet.")
    else:
        table = [{"Time (UTC)": item.get("created_at"), "Event": item.get("event_type"), "Actor": item.get("actor"), "Details": str(item.get("details") or {})[:280], "Record": item.get("draft_id") or item.get("employer_id") or "—"} for item in logs]
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True, height=540)
        st.download_button("Download visible audit log (CSV)", pd.DataFrame(table).to_csv(index=False).encode(), file_name="au_outreach_audit.csv", mime="text/csv")

elif page == "Settings":
    page_header("GUARDRAILS · CONFIGURATION", "Campaign settings", "Set the first campaign date and daily draft ceiling. Email account integration is intentionally removed.")
    start_raw = repo.get_setting("start_date", "2027-02-01")
    start_default = date.fromisoformat(start_raw) if isinstance(start_raw, str) else date(2027, 2, 1)
    with st.form("campaign_settings"):
        start_date = st.date_input("Earliest draft date", value=max(start_default, date(2027, 2, 1)), min_value=date(2027, 2, 1))
        saved_cap = int(repo.get_setting("daily_cap", 5))
        daily_cap = st.number_input("Maximum email drafts to prepare per day", min_value=1, max_value=100, value=min(100, max(1, saved_cap)), step=1)
        save = st.form_submit_button("Save campaign settings", type="primary")
    if save:
        repo.set_setting("start_date", start_date.isoformat())
        repo.set_setting("daily_cap", int(daily_cap))
        repo.log("campaign_settings_changed", {"start_date": start_date.isoformat(), "daily_draft_cap": int(daily_cap)})
        st.success("Campaign settings saved.")
    st.divider()
    st.markdown("### Database and AI status")
    st.write(f"**Database:** {repo.backend}")
    if repo.supabase:
        st.success("Supabase is configured. Confirm the employer, email_drafts, activity_logs, and campaign_settings tables exist.")
    else:
        st.warning("SQLite is preview-only. Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY before importing real employer data or deploying.")
    if secret("GROQ_API_KEY"):
        st.success(f"Groq drafting and browser search configured · {secret('GROQ_MODEL', 'openai/gpt-oss-20b')}")
    else:
        st.info("Groq is optional. Without a key, drafting uses an editable local template and discovery opens a direct search link.")
    st.markdown("### Manual email workflow")
    st.caption("No Outlook sign-in, access token, send permission, or email-sending endpoint is used. Word packs are created in memory for download. Copy, review, and send each message yourself, and optionally record that action in the draft review page.")
    st.markdown("### Privacy")
    st.caption("Keep the employer workbook, downloaded Word packs, APP_PASSWORD, Supabase service key, and Groq key out of Git and chat. The single shared password gate is intended for one controlled operator, not a multi-user identity system.")

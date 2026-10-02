from __future__ import annotations

import os
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

from storage import Repository
from outreach import FACULTIES, faculty_fit, create_email, search_organizations, start_outlook_device_flow, finish_outlook_device_flow, send_graph_email

st.set_page_config(page_title="AU Internship Outreach", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
:root { --ink:#11243a; --muted:#718095; --paper:#f4f6f8; --blue:#1468a0; --navy:#10253d; --line:#e3e8ed; --mint:#e5f5ec; }
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
.pill { display:inline-block;background:#e6f1f7;color:#155a85;padding:4px 9px;border-radius:99px;font-size:.72rem;font-weight:700;margin:2px 4px 2px 0; }
.approval { border:1px solid #f1c87e;background:#fff7e7;border-radius:14px;padding:14px 16px;color:#644716; }
.small-note { color:#758397;font-size:.82rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def secret(name: str, default: str = "") -> str:
    value=os.getenv(name)
    if value: return str(value)
    try: return str(st.secrets.get(name, default))
    except Exception: return default


def local_today() -> date:
    return datetime.now(ZoneInfo("Asia/Karachi")).date()


def require_login() -> bool:
    password=secret("APP_PASSWORD")
    if not password:
        st.session_state["au_demo_mode"]=True
        return True
    st.session_state["au_demo_mode"]=False
    if not st.session_state.get("au_authenticated"):
        st.markdown('<div class="eyebrow">AIR UNIVERSITY · H-11 CAMPUS</div><h1>Internship outreach desk</h1>',unsafe_allow_html=True)
        st.markdown('<p class="lead">A reviewed, auditable workspace for connecting students with summer opportunities.</p>',unsafe_allow_html=True)
        with st.form("login_form"):
            entered=st.text_input("Workspace password",type="password")
            submit=st.form_submit_button("Unlock workspace",type="primary")
            if submit:
                import hmac
                if hmac.compare_digest(entered,password): st.session_state["au_authenticated"]=True; st.rerun()
                else: st.error("That password did not match.")
        st.caption("Set APP_PASSWORD in Streamlit secrets before using real employer data.")
        return False
    return True


if not require_login(): st.stop()
repo=Repository()
if st.session_state.get("au_demo_mode"):
    existing=repo.list_employers()
    if not existing:
        demo_rows=[
            {"company_name":"Northstar Analytics (Demo)","email":"people@example.org","industry":"AI, Data and Robotic","country":"Pakistan","source":"synthetic demo","status":"new"},
            {"company_name":"Civic Futures Lab (Demo)","email":"internships@example.org","industry":"Public Policy and Research","country":"Pakistan","source":"synthetic demo","status":"new"},
            {"company_name":"Aero Systems Group (Demo)","email":"careers@example.org","industry":"Aerospace and Defence","country":"Pakistan","source":"synthetic demo","status":"new"},
        ]
        for row in demo_rows: row["program_fit"],row["fit_notes"]=faculty_fit(row.get("industry",""),row["company_name"])
        repo.upsert_employers(demo_rows)

st.sidebar.markdown('<div class="au-brand"><div class="au-mark">AU</div><div><div class="au-name">INTERNSHIP DESK</div><div class="au-sub">H-11 Campus · Summer 2027</div></div></div>',unsafe_allow_html=True)
page=st.sidebar.radio("WORKSPACE",["Overview","Employers","Find organizations","Email review","Activity log","Settings & integrations"],label_visibility="visible")
st.sidebar.divider()
st.sidebar.caption(f"Data store · {repo.backend}")
if st.session_state.get("au_demo_mode"):
    st.sidebar.caption("Demo contains only synthetic addresses. Import and send are locked.")
elif st.sidebar.button("Lock workspace"):
    st.session_state.pop("au_authenticated",None)
    st.session_state.pop("graph_access_token",None)
    st.session_state.pop("outlook_account",None)
    st.rerun()
if st.session_state.get("outlook_account"):
    st.sidebar.success(f"Outlook connected · {st.session_state['outlook_account']}")

employers=repo.list_employers()
drafts=repo.list_drafts()
by_id={str(x["id"]):x for x in employers}


def page_header(kicker: str, title: str, desc: str):
    st.markdown(f'<div class="eyebrow">{kicker}</div><h1>{title}</h1><p class="lead">{desc}</p>',unsafe_allow_html=True)


def display_fit(items):
    return ", ".join(items or []) or "Review manually"


if page=="Overview":
    page_header("OUTREACH OPERATIONS · SUMMER 2027","A careful first hello.","Review employer prospects, prepare thoughtful messages, and keep every decision visible before it leaves your Outlook account.")
    local_day=local_today()
    start_raw=repo.get_setting("start_date","2027-02-01")
    start_date=date.fromisoformat(start_raw) if isinstance(start_raw,str) else date(2027,2,1)
    cap=int(repo.get_setting("daily_cap",5))
    sent_today=repo.daily_sent_count(local_day)
    eligible=0
    for e in employers:
        if e.get("email") and e.get("status") not in ("do_not_contact","sent"):
            eligible+=1
    pending=sum(d.get("status")=="draft" for d in drafts)
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Employer records",len(employers),help="Includes contacts and saved organization prospects")
    m2.metric("Ready for review",pending)
    m3.metric("Sent today",f"{sent_today} / {cap}")
    m4.metric("Campaign opens",start_date.strftime("%b %Y"),help=f"No send before {start_date.strftime('%d %B %Y')}")
    st.write("")
    left,right=st.columns([1.35,.85],gap="large")
    with left:
        st.subheader("Today's workflow")
        with st.container(border=True):
            st.markdown("**01 · Select a verified organization**")
            st.caption("Use the uploaded employer list or review new organization-search results before saving.")
            st.markdown("**02 · Prepare an editable draft**")
            st.caption("Suggested faculty alignment is a starting point. Confirm the actual fit and the recipient.")
            st.markdown("**03 · Approve each message individually**")
            st.caption("The exact recipient, subject, and body are shown before the one-message send action.")
        st.markdown('<p class="small-note">A daily cap limits volume; it never substitutes for individual approval.</p>',unsafe_allow_html=True)
    with right:
        st.subheader("Campaign gate")
        if local_day<start_date:
            st.warning(f"Sending is locked until {start_date.strftime('%d %B %Y')}.")
        elif sent_today>=cap:
            st.warning("Daily send cap reached. No more messages can be sent today.")
        else:
            st.success(f"Campaign date reached · {cap-sent_today} individual send(s) remain under today's cap.")
        if not secret("SUPABASE_URL") or not secret("SUPABASE_SERVICE_ROLE_KEY"):
            st.info("Local SQLite is for preview only. Configure Supabase before importing real records or using Streamlit Cloud.")
        if not st.session_state.get("outlook_account"):
            st.info("Outlook sign-in is required before a send can happen.")
    st.subheader("Suggested faculty focus")
    fit_cols=st.columns(3)
    blurbs=["Business, management, finance, marketing, operations and related placements.","Policy, education, research, media, communication and community-facing roles.","Aerospace, aviation, security, defence, space and strategic-studies environments."]
    for col,name,blurb in zip(fit_cols,FACULTIES,blurbs):
        with col,st.container(border=True): st.markdown(f"**{name}**"); st.caption(blurb)

elif page=="Employers":
    page_header("LEAD MANAGEMENT · STEP 01","Employer directory","Import the provided workbook, review contact quality, and mark organizations you do not want contacted.")
    if st.session_state.get("au_demo_mode"):
        st.info("This preview is read-only and contains synthetic demo records. Add APP_PASSWORD and Supabase secrets to enable real-data intake.")
    elif not repo.supabase:
        st.warning("Real-data import is locked until Supabase is configured. Local SQLite is preview-only and may be ephemeral.")
    else:
        up=st.file_uploader("Upload employer sheet (Excel or CSV)",type=["xlsx","xls","csv"],help="The workbook is read locally by this Streamlit server; it is not added to the source repository.")
        if up:
            try:
                frame=pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up)
                st.caption(f"Preview · {len(frame):,} rows · {len(frame.columns)} columns")
                st.dataframe(frame.head(12),use_container_width=True,hide_index=True)
                if st.button(f"Import {len(frame):,} rows",type="primary",key="import_sheet"):
                    imported=[]; skipped=0
                    for _,r in frame.iterrows():
                        raw={str(k).strip().lower(): (None if pd.isna(v) else str(v).strip()) for k,v in r.to_dict().items()}
                        def pick(*keys):
                            return next((v for k,v in raw.items() if any(token in k for token in keys) and v),None)
                        email=pick("email")
                        if not email or not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$",email): skipped+=1; continue
                        company=pick("company name","company","organization","organisation")
                        if not company: skipped+=1; continue
                        industry=pick("industry","sector") or ""
                        position=pick("position","job title","role") or ""
                        fits,note=faculty_fit(industry,company,position)
                        imported.append({"source":pick("source") or up.name,"title":pick("title"),"first_name":pick("first name","firstname","given name"),"last_name":pick("last name","lastname","surname"),"position":position,"industry":industry,"company_name":company,"country":pick("country","territory"),"email":email,"phone":pick("phone","mobile"),"program_fit":fits,"fit_notes":note,"status":"new"})
                    added,updated=repo.upsert_employers(imported); repo.log("employer_import",{"file":up.name,"processed":len(imported),"added":added,"updated":updated,"skipped":skipped})
                    st.success(f"Import complete · {added} new · {updated} updated · {skipped} skipped for missing/invalid company or email."); st.rerun()
            except Exception as exc:
                st.error(f"Could not read/import this workbook: {exc}")
    st.divider()
    search=st.text_input("Search by company, industry, email, or contact",placeholder="Start typing a company or industry…")
    filtered=employers
    if search:
        term=search.lower(); filtered=[e for e in employers if term in " ".join(str(e.get(k) or "") for k in ("company_name","industry","email","first_name","last_name")).lower()]
    show=[]
    for e in filtered:
        show.append({"Company":e.get("company_name"),"Contact":(" ".join(x for x in [e.get("first_name"),e.get("last_name")] if x) or "—"),"Email":e.get("email") or "—","Industry":e.get("industry") or "—","Suggested faculty":display_fit(e.get("program_fit")),"Status":e.get("status","new")})
    st.dataframe(pd.DataFrame(show),use_container_width=True,hide_index=True,height=420)
    st.caption(f"Showing {len(filtered)} of {len(employers)} records. Suppressed contacts are excluded from sending.")
    choices=[e for e in employers if e.get("status")!="do_not_contact"]
    if choices and not st.session_state.get("au_demo_mode") and repo.supabase:
        selected_id=st.selectbox("Manage a contact",options=[str(e["id"]) for e in choices],format_func=lambda i:f"{by_id[i].get('company_name')} · {by_id[i].get('email') or 'no contact email'}")
        selected=by_id[selected_id]
        f1,f2=st.columns(2)
        with f1:
            st.caption(f"Fit note: {selected.get('fit_notes') or 'Not assessed'}")
            if st.button("Mark do not contact",key="suppress_contact"):
                repo.update_employer(selected_id,{"status":"do_not_contact"}); repo.log("contact_suppressed",{"company":selected.get("company_name")},employer_id=selected_id); st.rerun()
        with f2:
            with st.form("verified_contact_form"):
                contact_email=st.text_input("Verified HR / internship email",value=selected.get("email") or "")
                contact_first=st.text_input("Contact first name",value=selected.get("first_name") or "")
                contact_last=st.text_input("Contact last name",value=selected.get("last_name") or "")
                contact_position=st.text_input("Contact position",value=selected.get("position") or "")
                save_contact=st.form_submit_button("Save verified contact")
            if save_contact:
                if contact_email.strip() and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$",contact_email.strip()):
                    st.error("Enter a valid email or leave the field blank until verified.")
                else:
                    try:
                        normalized_email=contact_email.strip().lower() or None
                        same_recipient=normalized_email==((selected.get("email") or "").strip().lower() or None)
                        next_status=selected.get("status","prospect") if same_recipient and selected.get("status") in ("drafted","sent","do_not_contact") else ("new" if normalized_email else selected.get("status","prospect"))
                        repo.update_employer(selected_id,{"email":normalized_email,"first_name":contact_first.strip(),"last_name":contact_last.strip(),"position":contact_position.strip(),"status":next_status})
                        repo.log("contact_verified",{"email":contact_email.strip().lower() or None,"contact_name":" ".join(x for x in [contact_first.strip(),contact_last.strip()] if x)},employer_id=selected_id)
                        st.success("Contact details saved. Check the email source before drafting."); st.rerun()
                    except Exception as exc: st.error(f"Could not save contact details: {exc}")
            if selected.get("email") and selected.get("status") not in ("drafted","sent") and st.button("Create email draft",type="primary",key="create_from_employer"):
                fits=selected.get("program_fit") or FACULTIES
                subject,body,model=create_email(selected.get("company_name",""),selected.get("first_name",""),selected.get("industry",""),fits)
                draft=repo.create_draft({"employer_id":selected_id,"to_email":selected["email"],"subject":subject,"body_text":body,"program_fit":fits})
                repo.update_employer(selected_id,{"status":"drafted"}); repo.log("draft_created",{"model":model,"subject":subject},employer_id=selected_id,draft_id=draft["id"])
                st.success("Draft created. It will not be sent until you review and approve it."); st.rerun()

elif page=="Find organizations":
    page_header("PROSPECT DISCOVERY · STEP 02","Find relevant organizations","Search public web results by faculty and industry. Results are unverified; review the source before saving a prospect.")
    st.info("Discovery identifies organizations only. It does not scrape email addresses or contact anyone. With GROQ_API_KEY configured, the app uses Groq's browser-search model and returns links for human verification.")
    with st.form("search_form"):
        faculty=st.selectbox("Start from a faculty",FACULTIES)
        domain=st.text_input("Industry or employer type",placeholder="e.g., banks, policy think tanks, airlines, cybersecurity firms")
        country=st.text_input("Geography",value="Pakistan")
        limit=st.slider("Result count",3,12,8)
        do_search=st.form_submit_button("Search public web",type="primary")
    if do_search:
        if not domain.strip(): st.warning("Add an industry or employer type so results are relevant.")
        elif not secret("GROQ_API_KEY"):
            query=f"organizations {domain} internships careers {country}"
            url="https://www.google.com/search?q="+quote_plus(query)
            st.warning("In-app web search needs a Groq API key. You can still open a browser search and add reviewed organizations manually.")
            st.link_button("Open Google search results",url)
        else:
            query=f"organizations {domain} internships careers {country}"
            with st.spinner("Searching public organization results…"):
                try:
                    results=search_organizations(query,limit)
                    st.session_state["org_search_results"]={"items":results,"faculty":faculty,"domain":domain,"query":query,"country":country}
                    repo.log("organization_search",{"query":query,"results":len(results)})
                except Exception as exc:
                    st.error(f"Search could not complete right now: {exc}. Try again later or add a known organization manually.")
    payload=st.session_state.get("org_search_results")
    if payload:
        items=payload.get("items",[])
        if not items: st.warning("No search results returned. Try a broader domain.")
        else:
            st.write(f"**{len(items)} results** · {payload.get('domain')} · {payload.get('faculty')}")
            for i,item in enumerate(items):
                with st.container(border=True):
                    c1,c2=st.columns([.82,.18])
                    with c1:
                        st.markdown(f"**{item['title']}**")
                        st.caption(item.get("snippet") or "No description in result")
                        st.markdown(f"[Review source]({item['url']})")
                    with c2:
                        if st.button("Save prospect",key=f"save_result_{i}",disabled=bool(st.session_state.get("au_demo_mode") or not repo.supabase)):
                            company=re.split(r"\s[|–—-]\s",item["title"])[0].strip()[:180]
                            row={"company_name":company,"industry":payload.get("domain"),"website":item["url"],"source_url":item["url"],"source":"public web search · human-reviewed","country":payload.get("country","Pakistan"),"status":"prospect","program_fit":[payload.get("faculty")],"fit_notes":"Unverified web result. Confirm company, official website, and relevance before adding a contact or drafting outreach."}
                            added,_=repo.upsert_employers([row]); repo.log("prospect_saved",{"company":company,"source_url":item["url"]})
                            st.success("Prospect saved without an email address."); st.rerun()
    st.divider()
    with st.expander("Add a known organization manually"):
        if st.session_state.get("au_demo_mode"):
            st.caption("Manual entry is disabled in demo mode.")
        elif not repo.supabase:
            st.caption("Configure Supabase before saving durable prospect records.")
        else:
            with st.form("manual_prospect"):
                company=st.text_input("Organization name")
                website=st.text_input("Official website or source URL")
                industry=st.text_input("Industry")
                fit=st.multiselect("Possible faculty areas",FACULTIES)
                save=st.form_submit_button("Save as unverified prospect")
            if save and company.strip():
                fits=fit or faculty_fit(industry,company)[0]
                repo.upsert_employers([{"company_name":company.strip(),"website":website.strip() or None,"source_url":website.strip() or None,"industry":industry,"source":"manual prospect","status":"prospect","program_fit":fits,"fit_notes":"User-entered prospect; verify employer details and contact before drafting."}])
                repo.log("prospect_manual",{"company":company.strip()}); st.success("Prospect saved."); st.rerun()

elif page=="Email review":
    page_header("HUMAN APPROVAL · STEP 03","Review before sending","Every message is a separate decision. Review the exact destination, subject, and body; no email is sent during drafting.")
    if st.session_state.get("au_demo_mode"):
        st.warning("Demo mode: message sending and imports are disabled. Demo addresses use example.org.")
    start_raw=repo.get_setting("start_date","2027-02-01"); start_date=date.fromisoformat(start_raw) if isinstance(start_raw,str) else date(2027,2,1)
    cap=int(repo.get_setting("daily_cap",5)); today=local_today(); sent_today=repo.daily_sent_count(today)
    if today<start_date: st.warning(f"Campaign sending is locked until {start_date.strftime('%d %B %Y')}.")
    if sent_today>=cap: st.error("Today's send cap has been reached.")
    queue=[d for d in drafts if d.get("status") in ("draft","send_error")]
    if not queue: st.info("No message drafts awaiting review. Create a draft from the Employers page after verifying the contact.")
    else:
        ids=[str(d["id"]) for d in queue]
        selected_id=st.selectbox("Choose one message",ids,format_func=lambda i:f"{by_id.get(str(next((d['employer_id'] for d in queue if str(d['id'])==i),'')),{}).get('company_name','Employer')} · {next((d.get('to_email','') for d in queue if str(d['id'])==i),'')}")
        draft=next(d for d in queue if str(d["id"])==selected_id)
        employer=by_id.get(str(draft.get("employer_id")),{})
        c1,c2=st.columns([.8,.2])
        with c1:
            st.markdown(f"#### {employer.get('company_name','Employer')}")
            st.caption(f"Suggested faculty fit: {display_fit(draft.get('program_fit'))} · Contact status: {employer.get('status','unknown')}")
        with c2: st.metric("Daily limit",f"{sent_today} / {cap}")
        with st.form("review_email_form"):
            recipient=st.text_input("Recipient email",value=draft.get("to_email",""))
            subject=st.text_input("Subject",value=draft.get("subject",""))
            body=st.text_area("Email body",value=draft.get("body_text",""),height=290)
            signature=repo.get_setting("signature_text","")
            if signature:
                st.caption("Signature will be appended to the message as configured in Settings.")
            reviewed=st.checkbox("I reviewed the exact recipient, subject, and message above. I approve sending this one email.")
            save=st.form_submit_button("Save draft changes")
            send=st.form_submit_button("Approve & send this email",type="primary")
        if save:
            if not recipient.strip() or not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$",recipient.strip()): st.error("Enter a valid recipient email.")
            elif not subject.strip() or not body.strip(): st.error("Subject and message body are required.")
            else:
                repo.update_draft(selected_id,{"to_email":recipient,"subject":subject,"body_text":body,"status":"draft"})
                repo.log("draft_edited",{"recipient":recipient,"subject":subject},employer_id=draft.get("employer_id"),draft_id=selected_id); st.success("Draft saved; it still needs individual approval."); st.rerun()
        if send:
            errors=[]
            if st.session_state.get("au_demo_mode"): errors.append("Demo mode cannot send.")
            if not reviewed: errors.append("Check the approval box after reviewing the exact message.")
            if today<start_date: errors.append(f"Sending is locked until {start_date.strftime('%d %B %Y')}.")
            if sent_today>=cap: errors.append("Daily cap reached.")
            if employer.get("status")=="do_not_contact": errors.append("This employer is marked do not contact.")
            if employer.get("status")=="sent": errors.append("This employer already has a recorded send; duplicate outreach is blocked.")
            if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$",recipient.strip()): errors.append("Recipient email is invalid.")
            if not subject.strip() or not body.strip(): errors.append("Subject and body are required.")
            if not st.session_state.get("graph_access_token"): errors.append("Sign in to Outlook in Settings & integrations first.")
            if errors:
                for error in errors: st.error(error)
            else:
                # Persist exact reviewed content and approval record immediately before the send attempt.
                now=datetime.now(ZoneInfo("UTC")).isoformat()
                repo.update_draft(selected_id,{"to_email":recipient,"subject":subject,"body_text":body,"approved_by":st.session_state.get("outlook_account","operator"),"approved_at":now})
                repo.log("email_approved",{"recipient":recipient,"subject":subject,"approval":"operator checkbox"},employer_id=draft.get("employer_id"),draft_id=selected_id)
                try:
                    result=send_graph_email(recipient,subject,body,signature)
                    repo.update_draft(selected_id,{"status":"sent","sent_at":datetime.now(ZoneInfo("UTC")).isoformat(),"outlook_message_id":result.get("request_id"),"error_text":None})
                    repo.update_employer(str(draft.get("employer_id")),{"status":"sent"})
                    repo.log("email_sent",{"recipient":recipient,"subject":subject,"graph_request_id":result.get("request_id")},employer_id=draft.get("employer_id"),draft_id=selected_id)
                    st.success("Message sent and recorded in the audit log."); st.rerun()
                except Exception as exc:
                    repo.update_draft(selected_id,{"status":"send_error","error_text":str(exc)[:1500]})
                    repo.log("email_send_error",{"error":str(exc)[:1000],"recipient":recipient},employer_id=draft.get("employer_id"),draft_id=selected_id)
                    st.error(f"Send failed; nothing is marked as sent. Review the error and retry only after confirming the mailbox status. {exc}")
        st.markdown('<div class="approval"><b>Approval boundary:</b> this button sends only the single reviewed message above. There is no bulk send, and the campaign date and daily cap are checked again at send time.</div>',unsafe_allow_html=True)
        st.caption(f"Signature preview appended: {signature or 'No signature configured — add it in Settings.'}")

elif page=="Activity log":
    page_header("AUDIT TRAIL · STEP 04","Activity log","A record of imports, prospect discovery, draft changes, individual approvals, and send outcomes.")
    logs=repo.list_logs(500)
    if not logs: st.info("No activity recorded yet.")
    else:
        table=[]
        for item in logs:
            table.append({"Time (UTC)":item.get("created_at"),"Event":item.get("event_type"),"Actor":item.get("actor"),"Details":str(item.get("details") or {})[:280],"Record":item.get("draft_id") or item.get("employer_id") or "—"})
        st.dataframe(pd.DataFrame(table),use_container_width=True,hide_index=True,height=540)
        st.download_button("Download visible audit log (CSV)",pd.DataFrame(table).to_csv(index=False).encode(),file_name="au_outreach_audit.csv",mime="text/csv")

elif page=="Settings & integrations":
    page_header("GUARDRAILS · CONFIGURATION","Settings & integrations","Set the campaign window, a conservative daily ceiling, approved signature text, and the services used by this private workspace.")
    st.markdown("### Campaign controls")
    start_raw=repo.get_setting("start_date","2027-02-01"); start_default=date.fromisoformat(start_raw) if isinstance(start_raw,str) else date(2027,2,1)
    with st.form("campaign_settings"):
        start_date=st.date_input("Earliest send date",value=max(start_default,date(2027,2,1)),min_value=date(2027,2,1))
        daily_cap=st.number_input("Maximum individually approved sends per day",min_value=1,max_value=100,value=int(repo.get_setting("daily_cap",5)),step=1)
        signature=st.text_area("Signature to append to outgoing messages",value=repo.get_setting("signature_text",""),height=120,help="Graph API does not inherit the signature saved in Outlook compose. Paste the approved text here.")
        save=st.form_submit_button("Save campaign settings",type="primary")
    if save:
        repo.set_setting("start_date",start_date.isoformat()); repo.set_setting("daily_cap",int(daily_cap)); repo.set_setting("signature_text",signature.strip())
        repo.log("campaign_settings_changed",{"start_date":start_date.isoformat(),"daily_cap":int(daily_cap),"signature_configured":bool(signature.strip())})
        st.success("Campaign settings saved.")
    st.divider()
    st.markdown("### Outlook sign-in")
    st.caption("Delegated Microsoft Graph access uses your signed-in Outlook identity and the Mail.Send permission. No message is sent during sign-in.")
    tenant=secret("MICROSOFT_TENANT_ID","common")
    if st.session_state.get("outlook_account"):
        st.success(f"Signed in as {st.session_state['outlook_account']}")
        if st.button("Sign out of this app session"):
            st.session_state.pop("graph_access_token",None); st.session_state.pop("outlook_account",None); st.session_state.pop("outlook_device_flow",None); st.rerun()
    else:
        if not secret("MICROSOFT_CLIENT_ID"):
            st.warning("Set MICROSOFT_CLIENT_ID in Streamlit secrets after registering a Microsoft Entra public-client app.")
        if st.button("Start Outlook device sign-in",type="primary",disabled=not bool(secret("MICROSOFT_CLIENT_ID"))):
            try:
                flow=start_outlook_device_flow(tenant)
                st.info(f"On another tab/device, open {flow.get('verification_uri','https://microsoft.com/devicelogin')} and enter code **{flow.get('user_code')}**. Then return here and choose Complete sign-in.")
            except Exception as exc: st.error(str(exc))
        if st.session_state.get("outlook_device_flow") and st.button("Complete sign-in after entering the code"):
            try:
                with st.spinner("Waiting for Microsoft sign-in…"):
                    result=finish_outlook_device_flow(tenant)
                st.success("Outlook sign-in succeeded."); st.rerun()
            except Exception as exc: st.error(str(exc))
    st.divider()
    st.markdown("### Storage and AI status")
    st.write(f"**Database:** {repo.backend}")
    if repo.supabase: st.success("Supabase is configured. Confirm `schema.sql` has been applied.")
    else: st.warning("SQLite is local preview storage only. Configure `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` before importing real employer data or deploying.")
    if secret("GROQ_API_KEY"): st.success(f"Optional Groq drafting configured · {secret('GROQ_MODEL','llama-3.3-70b-versatile')}")
    else: st.info("Groq is optional. Without a key, drafts use a transparent editable template.")
    st.markdown("### Privacy note")
    st.caption("Use the private repository and private Streamlit deployment settings. Keep the employer workbook, APP_PASSWORD, Supabase service key, and Groq key out of Git and chat. The single shared password gate is intended for one controlled operator; it is not a multi-user identity or authorization system.")

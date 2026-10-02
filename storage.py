from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone, date, time, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "local.db"


def _secret(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return str(value)
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self):
        self.supabase = None
        url, key = _secret("SUPABASE_URL"), _secret("SUPABASE_SERVICE_ROLE_KEY")
        if url and key:
            try:
                from supabase import create_client
                self.supabase = create_client(url, key)
            except Exception as exc:
                st.error(f"Supabase connection could not be initialized: {exc}")
        if self.supabase is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()

    @property
    def backend(self) -> str:
        return "Supabase Postgres" if self.supabase else "Local SQLite (preview only)"

    def _connect(self):
        conn = sqlite3.connect(DB_PATH, timeout=20)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self):
        with self._connect() as c:
            c.executescript("""
            create table if not exists employers(
              id text primary key, source text, title text, first_name text, last_name text,
              position text, industry text, company_name text not null, country text, email text unique,
              phone text, website text, source_url text, program_fit text not null default '[]',
              fit_notes text, status text not null default 'new', created_at text, updated_at text
            );
            create table if not exists email_drafts(
              id text primary key, employer_id text not null, to_email text not null, subject text not null,
              body_text text not null, program_fit text not null default '[]', status text not null default 'draft',
              created_by text, approved_by text, approved_at text, sent_at text,
              error_text text, created_at text, updated_at text
            );
            create table if not exists activity_logs(
              id text primary key, event_type text not null, employer_id text, draft_id text,
              actor text not null, details text not null default '{}', created_at text not null
            );
            create table if not exists campaign_settings(
              key text primary key, value text not null, updated_at text not null
            );
            """)

    @staticmethod
    def _employer_out(row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        if isinstance(row.get("program_fit"), str):
            try: row["program_fit"] = json.loads(row["program_fit"])
            except Exception: row["program_fit"] = []
        return row

    @staticmethod
    def _draft_out(row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        if isinstance(row.get("program_fit"), str):
            try: row["program_fit"] = json.loads(row["program_fit"])
            except Exception: row["program_fit"] = []
        return row

    def list_employers(self) -> list[dict[str, Any]]:
        if self.supabase:
            return [self._employer_out(x) for x in (self.supabase.table("employers").select("*").order("updated_at", desc=True).limit(5000).execute().data or [])]
        with self._connect() as c:
            return [self._employer_out(dict(r)) for r in c.execute("select * from employers order by updated_at desc").fetchall()]

    def upsert_employers(self, rows: list[dict[str, Any]]) -> tuple[int, int]:
        inserted = updated = 0
        for raw in rows:
            item = {k: raw.get(k) for k in ("source","title","first_name","last_name","position","industry","company_name","country","email","phone","website","source_url","program_fit","fit_notes","status")}
            item["company_name"] = str(item.get("company_name") or "").strip()
            if not item["company_name"]:
                continue
            item["email"] = (str(item["email"]).strip().lower() if item.get("email") else None)
            item["program_fit"] = item.get("program_fit") or []
            item["status"] = item.get("status") or ("prospect" if not item["email"] else "new")
            item["source"] = item.get("source") or "import"
            item["updated_at"] = _now()
            if self.supabase:
                if item["email"]:
                    existing = self.supabase.table("employers").select("id,status").eq("email", item["email"]).limit(1).execute().data or []
                    if existing and existing[0].get("status") == "do_not_contact": item["status"] = "do_not_contact"
                    item["id"] = existing[0]["id"] if existing else str(uuid.uuid4())
                    item["created_at"] = _now() if not existing else None
                    item = {k:v for k,v in item.items() if v is not None}
                    self.supabase.table("employers").upsert(item, on_conflict="email").execute()
                    updated += int(bool(existing)); inserted += int(not existing)
                else:
                    item["id"] = str(uuid.uuid4()); item["created_at"] = _now()
                    self.supabase.table("employers").insert(item).execute(); inserted += 1
            else:
                with self._connect() as c:
                    old = c.execute("select id,status from employers where email=?", (item["email"],)).fetchone() if item["email"] else None
                    if old:
                        item["id"] = old["id"]
                        if old["status"] == "do_not_contact": item["status"] = "do_not_contact"
                        c.execute("""update employers set source=:source,title=:title,first_name=:first_name,last_name=:last_name,position=:position,industry=:industry,company_name=:company_name,country=:country,phone=:phone,website=:website,source_url=:source_url,program_fit=:program_fit,fit_notes=:fit_notes,status=coalesce(:status,'new'),updated_at=:updated_at where id=:id""", {**item,"program_fit":json.dumps(item["program_fit"]),"id":old["id"]})
                        updated += 1
                    else:
                        item["id"] = str(uuid.uuid4()); item["created_at"] = _now()
                        payload = {**item,"program_fit":json.dumps(item["program_fit"])}
                        cols = ",".join(payload); marks = ",".join([":"+k for k in payload])
                        c.execute(f"insert into employers ({cols}) values ({marks})", payload)
                        inserted += 1
        return inserted, updated

    def update_employer(self, employer_id: str, changes: dict[str, Any]):
        allowed = {"status","email","first_name","last_name","position","country","program_fit","fit_notes","company_name","website","industry","phone","source_url"}
        data = {k:v for k,v in changes.items() if k in allowed}
        data["updated_at"] = _now()
        if "email" in data and data["email"]:
            data["email"] = data["email"].strip().lower()
        if self.supabase:
            self.supabase.table("employers").update(data).eq("id", employer_id).execute()
        else:
            data["id"] = employer_id
            if "program_fit" in data: data["program_fit"] = json.dumps(data["program_fit"])
            with self._connect() as c:
                c.execute("update employers set "+", ".join(f"{k}=:{k}" for k in data if k!="id")+" where id=:id", data)

    def create_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        item = {"id":str(uuid.uuid4()),"employer_id":draft["employer_id"],"to_email":draft["to_email"],"subject":draft["subject"],"body_text":draft["body_text"],"program_fit":draft.get("program_fit",[]),"status":"draft","created_by":"operator","created_at":_now(),"updated_at":_now()}
        if self.supabase:
            self.supabase.table("email_drafts").insert(item).execute()
        else:
            payload={**item,"program_fit":json.dumps(item["program_fit"])}
            with self._connect() as c:
                cols=",".join(payload); marks=",".join([":"+k for k in payload])
                c.execute(f"insert into email_drafts ({cols}) values ({marks})",payload)
        return item

    def list_drafts(self, statuses: list[str] | None = None) -> list[dict[str, Any]]:
        if self.supabase:
            q=self.supabase.table("email_drafts").select("*").order("created_at",desc=True).limit(1000)
            if statuses: q=q.in_("status",statuses)
            return [self._draft_out(x) for x in (q.execute().data or [])]
        with self._connect() as c:
            if statuses:
                marks=",".join("?" for _ in statuses)
                rows=c.execute(f"select * from email_drafts where status in ({marks}) order by created_at desc",statuses).fetchall()
            else: rows=c.execute("select * from email_drafts order by created_at desc").fetchall()
            return [self._draft_out(dict(r)) for r in rows]

    def update_draft(self, draft_id: str, changes: dict[str, Any]):
        allowed={"to_email","subject","body_text","program_fit","status","approved_by","approved_at","sent_at"}
        data={k:v for k,v in changes.items() if k in allowed}; data["updated_at"]=_now()
        if "to_email" in data: data["to_email"]=data["to_email"].strip().lower()
        if self.supabase:
            self.supabase.table("email_drafts").update(data).eq("id",draft_id).execute()
        else:
            if "program_fit" in data: data["program_fit"]=json.dumps(data["program_fit"])
            data["id"]=draft_id
            with self._connect() as c:
                c.execute("update email_drafts set "+", ".join(f"{k}=:{k}" for k in data if k!="id")+" where id=:id",data)

    def log(self, event_type: str, details: dict[str, Any] | None = None, employer_id: str | None = None, draft_id: str | None = None, actor: str = "operator"):
        item={"id":str(uuid.uuid4()),"event_type":event_type,"employer_id":employer_id,"draft_id":draft_id,"actor":actor,"details":details or {},"created_at":_now()}
        if self.supabase: self.supabase.table("activity_logs").insert(item).execute()
        else:
            payload={**item,"details":json.dumps(item["details"])}
            with self._connect() as c:
                cols=",".join(payload); marks=",".join([":"+k for k in payload])
                c.execute(f"insert into activity_logs ({cols}) values ({marks})",payload)

    def list_logs(self, limit: int = 200) -> list[dict[str, Any]]:
        if self.supabase: return self.supabase.table("activity_logs").select("*").order("created_at",desc=True).limit(limit).execute().data or []
        with self._connect() as c:
            rows=c.execute("select * from activity_logs order by created_at desc limit ?",(limit,)).fetchall()
            result=[]
            for r in rows:
                d=dict(r)
                try: d["details"]=json.loads(d["details"])
                except Exception: pass
                result.append(d)
            return result

    def get_setting(self, key: str, default: Any = None) -> Any:
        if self.supabase:
            rows=self.supabase.table("campaign_settings").select("value").eq("key",key).limit(1).execute().data or []
            return rows[0]["value"] if rows else default
        with self._connect() as c:
            row=c.execute("select value from campaign_settings where key=?",(key,)).fetchone()
            if not row: return default
            try: return json.loads(row["value"])
            except Exception: return default

    def set_setting(self, key: str, value: Any):
        item={"key":key,"value":value,"updated_at":_now()}
        if self.supabase: self.supabase.table("campaign_settings").upsert(item,on_conflict="key").execute()
        else:
            with self._connect() as c:
                c.execute("insert into campaign_settings(key,value,updated_at) values(?,?,?) on conflict(key) do update set value=excluded.value, updated_at=excluded.updated_at",(key,json.dumps(value),_now()))

    def daily_draft_count(self, day: date) -> int:
        local_start=datetime.combine(day,time.min,tzinfo=ZoneInfo("Asia/Karachi"))
        start=local_start.astimezone(timezone.utc).isoformat()
        end=(local_start+timedelta(days=1)).astimezone(timezone.utc).isoformat()
        if self.supabase:
            rows=self.supabase.table("email_drafts").select("id",count="exact").gte("created_at",start).lt("created_at",end).neq("status","discarded").execute()
            return int(rows.count or 0)
        with self._connect() as c:
            return int(c.execute("select count(*) from email_drafts where status!='discarded' and created_at>=? and created_at<?",(start,end)).fetchone()[0])

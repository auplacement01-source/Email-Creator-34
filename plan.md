# Air University Internship Outreach — Implementation Plan

## Product scope
A Streamlit operations dashboard to import the user's employer workbook, search for additional organizations, match leads to Air University's AUSOM, Social Sciences, and Aerospace & Strategic Studies faculties, generate tailored summer-2027 email drafts, require human review/approval before any individual send, and preserve auditable employer/draft/send records. The operational start date defaults to **1 February 2027** and the daily send ceiling defaults to **5**. No unattended or automatic sending is implemented.

## Architecture
- **Streamlit** server-rendered UI; app password gate before any employer/draft data is displayed when deployed with real data.
- **Supabase Postgres** via server-side `supabase-py` when configured; local SQLite is used only for local preview/development. The Supabase service-role secret is never placed in browser code or committed.
- **Employer intake** supports XLSX/CSV upload and column-name normalization. The supplied workbook remains outside Git because it contains 400 named employer contacts and email addresses.
- **Discovery** uses Groq's documented GPT-OSS built-in browser search when `GROQ_API_KEY` is configured; otherwise it opens a direct browser-search link for manual review. Results are unverified organization leads; the user reviews and adds them. The app does not harvest personal email addresses.
- **Matching** is an editable keyword-to-faculty heuristic, presented as a suggestion rather than a claim about individual student qualifications.
- **Drafting** uses Groq only if a key is configured; otherwise a transparent local template. Drafts are editable and are never sent as a side effect of generation.
- **Outlook** uses Microsoft Graph delegated device-code sign-in with delegated `Mail.Send`. A person signs in and checks each exact recipient, subject, and body before the individual send action. No batch-send, background schedule, or automatic send path exists.
- **Audit trail** records imports/discovery actions, draft creation/edits, approvals, send results/errors, and daily counts.

## Project structure
- `app.py` — Streamlit navigation, dashboard, lead intake/discovery, review, settings, safety gates.
- `storage.py` — SQLite/Supabase repository abstraction and audit log operations.
- `outreach.py` — faculty-fit mapping, draft generation, Groq call, Microsoft Graph device auth/send helpers.
- `schema.sql` — Supabase tables, indexes, and row-level-security defaults.
- `.streamlit/secrets.toml.example` — deployment secret names/placeholders only.
- `requirements.txt`, `README.md`, `.gitignore` — reproducible setup and deployment guidance; employer contact data and secrets are excluded.

## Design direction
- **Movement:** editorial civic-tech meets university career-services operations.
- **Core principles:** approval visible at every consequential transition; calm hierarchy; data provenance; editable automation rather than black-box automation.
- **Color philosophy:** deep university navy for trust, crisp indigo for active decisions, warm ivory for paper-like review surfaces, and restrained green/amber for status.
- **Layout paradigm:** narrow persistent navigation, a wide workbench with a strong page title and compact status rail; review tasks use a two-column decision-and-preview arrangement.
- **Signature elements:** numbered workflow markers, faculty-fit chips, and an unmistakable approval bar for every outbound email.
- **Interaction philosophy:** draft, inspect, then approve; no control that sends silently or in bulk.
- **Animation:** minimal, short status transitions only, respecting reduced-motion preferences.
- **Typography:** system sans for controls and tables, serif display headings for editorial warmth; clear 12/14/18/28/36px hierarchy.
- **Brand essence:** a careful internship-placement desk for Air University H-11 Campus, built to turn employer data into reviewed, accountable outreach. Personality: precise, collegial, dependable.
- **Brand voice:** specific and restrained. Examples: “Review each message before it leaves your account.” “A suggested faculty fit is a starting point—not a promise about any student.”
- **Wordmark/logo:** custom AU monogram in a square navy tile with a fine trajectory stroke; no third-party logo asset is required for this internal system.
- **Signature color:** Air-blue `#1468A0`.

## Integration constraints
GitHub, Outlook Mail, and Supabase connector enablement were offered but not accepted in this session. This local project is prepared for later GitHub/Streamlit deployment, while integrations require the user's own deployment secrets and Microsoft/Supabase setup. The current temporary preview will contain only synthetic demo contacts, never the attached employer sheet.

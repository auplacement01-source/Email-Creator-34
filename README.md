# Air University Internship Outreach

A Streamlit dashboard for reviewing employer leads and preparing one-at-a-time summer internship outreach for Air University H-11 Campus. It supports Faculty of AUSOM, Faculty of Social Sciences, and Faculty of Aerospace and Strategic Studies.

## Safety by design

- No background sender, timed sender, batch-send control, or send-on-draft behavior is implemented.
- Every send is gated by the campaign start date (default **1 February 2027**), the daily cap (default **5**), contact status, Outlook sign-in, and an explicit checked review of the exact recipient, subject, and body.
- Internet-discovered organizations are unverified prospects. Discovery does not harvest or infer personal email addresses; a human reviews each result and adds a contact separately.
- A prospect must receive a manually verified HR/internship email in the employer directory before the app enables draft creation.
- Suggested faculty fit is a keyword-based hint, not a claim that any individual student meets an employer's requirements.
- Activity records include imports, discovery, draft creation/edits, approvals, and send results/errors.
- The supplied workbook contains 400 named employer contacts. **Do not commit it to GitHub.** Import it through the app after configuring access and Supabase.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets locally; do not commit secrets.toml.
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Without secrets, the app opens a synthetic, read-only demo and stores any demo state in ignored `data/local.db`. Local SQLite is not suitable for production persistence.

## Supabase setup

1. Create a Supabase project.
2. Open **SQL Editor** and run [`schema.sql`](schema.sql).
3. In Streamlit secrets, set `SUPABASE_URL` and the server-only `SUPABASE_SERVICE_ROLE_KEY` (Supabase calls this a secret/service-role key). Never put it in frontend code, a public repository, a browser, or a chat message. Tables have RLS enabled and no public policies; only the protected Streamlit server should use this key.
4. Set a long random `APP_PASSWORD`. The password gate must be enabled for real employer records. Streamlit's shared password gate is suitable for a controlled single-operator tool, not a multi-user identity system.

## Outlook setup

1. In Microsoft Entra, register a public-client application for the tenant/account that will send mail. Enable device-code/public-client flow according to your organization's policy.
2. Add delegated Microsoft Graph permissions `User.Read` and `Mail.Send`; obtain admin consent if the tenant requires it.
3. Set `MICROSOFT_CLIENT_ID` and optionally `MICROSOFT_TENANT_ID` (`common` by default) in Streamlit secrets.
4. In **Settings & integrations**, start the device-code sign-in and complete it with the Outlook account that should send the email.
5. Review and save the signature text in the app. **Microsoft Graph sending does not open Outlook's compose window, so the signature already saved in Outlook's compose box is not automatically inserted.** Copy the approved signature into the app's signature setting and verify it in every preview.

The app calls `POST https://graph.microsoft.com/v1.0/me/sendMail` with delegated `Mail.Send`. Outlook/Exchange may apply tenant send limits and policies.

## Groq drafting and organization search

Set `GROQ_API_KEY` in server secrets. The app uses Groq's `openai/gpt-oss-20b` built-in `browser_search` for organization discovery; the key stays server-side. Search output is unverified and each source link must be reviewed before saving a prospect. With no key, the page opens a direct Google search link and supports manual prospect entry after Supabase is configured. The key is also used for optional AI email drafting; the default is `openai/gpt-oss-20b`, and `GROQ_MODEL` can override it. With no key, the app uses a clearly labeled local template. AI output is only a draft and must be checked and edited before approval.

Browser search does not return contact emails or phone numbers to the app. It returns organization names, short source descriptions, and URLs for human review; the user enters any contact email separately.

## Streamlit Community Cloud deployment

1. Create a **private** GitHub repository (the GitHub connector was not enabled in this build session, so no repository was created or pushed).
2. Add this project source to the repository; check that `.gitignore` excludes the employer workbook, `.streamlit/secrets.toml`, `.env`, and local DB.
3. In Streamlit Community Cloud, deploy `app.py` and add the secrets described above in the app's Secrets settings.
4. Run `schema.sql` in Supabase before importing personal data. Confirm login/password gate and verify Outlook device sign-in using a test message sent to an address you control before any employer outreach.
5. Upload `AU_QSEmployerData2028.xlsx` inside the authenticated app, inspect the preview, then import. Do not include the XLSX in the Git repository.

## Source references

- [Microsoft Graph `user: sendMail`](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0) — delegated `Mail.Send` is the least-privileged send permission.
- [Microsoft identity platform device code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code)
- [Supabase Python initialization](https://supabase.com/docs/reference/python/initializing)
- [Supabase Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Groq Browser Search API](https://console.groq.com/docs/tool-use/built-in-tools/browser-search)

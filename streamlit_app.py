import streamlit as st
import requests
from datetime import datetime
from openai import OpenAI
import smtplib
from email.mime.text import MIMEText

# --- SECRETS ---
AIRTABLE_PAT = st.secrets["AIRTABLE_PAT"]
AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
AIRTABLE_TABLE_NAME = "MonthlyThemes"
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_PAT}",
    "Content-Type": "application/json"
}

# --- SHARED PROMPT BUILDER ---
def build_prompt(subject, description, segment, extra=None):
    personas = {
        "Pre-Retiree": (
            "A couple in their late 50s in South East QLD. "
            "They’re financially comfortable but time-poor. "
            "They value clarity, simplicity, and confidence about the future. "
        ),
        "Retiree": (
            "A couple in their mid to late 60s in South East QLD. "
            "They're thoughtful, detail-focused, and value peace of mind. "
        )
    }
    base_prompt = f"""Write a marketing email suitable for Australian {segment.lower()} prospects.
Subject: {subject}
Theme description: {description}
Persona: {personas[segment]}

You are writing on behalf of Hatch Financial Planning, based in Logan, Queensland. Your audience is individuals or couples aged 50–65 with at least $1 million in investable assets (excluding their primary residence). They are time-poor professionals or business owners who are looking for clarity, confidence, and personal planning around retirement. Their question isn’t “Can we retire?” but “Can we afford to say yes to the life we want?”
Your job is to write engaging, easy-to-read emails (~400 words) that speak directly to these people. Each email should address a core belief or misconception they may have—like “We’ve done well, so we must be on track,” or “It’s too early to get advice.” Use the STAR method (Situation, Trouble, Action, Result) to structure any anecdotes or transformations. Emphasise the Action and Result phases to ensure clarity and usefulness.
Tone: Professional, warm, and clear. Be direct, never salesy. Avoid fluff, hype, or clichés. Keep grammar simple and natural. Use contractions and conversational language. Vary sentence length for rhythm, but keep most sentences short and punchy.
Avoid: Promotional copy, jargon, complex syntax, and AI-signature phrases like “Let’s dive into...” or “Unlock your potential.” Never make recommendations. Never assume the reader wants to buy.
Always include an actionable takeaway—something the reader can use to reflect, plan, or clarify their thinking even if they don’t reach out. End with a friendly, non-salesy P.S. that naturally links to Shane’s diary.
Examples of characters you’re writing for:
A semi-retired engineer and his partner who run a business, wondering if they can travel more
A retired couple with strong super balances and simple tastes, focused on using their money wisely
Sample beliefs to challenge:
“We don’t need a plan—we’re doing fine.”
“Advice is for people with more money.”
“We’ll figure it out when we’re closer to retirement.”
“Financial advice is just about spreadsheets.”
Do not use any formatting like **bold**, *italics*, bullet points, numbered lists, or code blocks.
Write everything in plain text, as it would appear in a basic email editor.
Put each sentence on a new line.
Don't directly reference the reader's age or location as it makes it too specific.
Include a soft P.S. with a CTA.
Use Australian English. Do not use em or en dashes — use normal hyphens (-) only and sparingly so."""
    if extra:
        base_prompt += f"\n\nAdditional instructions: {extra}"
    return base_prompt


# --- HELPERS ---
def get_month():
    return datetime.now().strftime("%B %Y")

def fetch_segment_record(segment):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    params = {
        "filterByFormula": f"AND(Segment = '{segment}', Month = '{get_month()}')",
        "pageSize": 10
    }
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        st.error(f"Error fetching records for {segment}: {response.text}")
        return []
    return response.json().get("records", [])

def update_status(segment, new_record_id):
    current_month = get_month()
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    params = {
        "filterByFormula": f"AND(Segment = '{segment}', Status = 'selected', Month = '{current_month}')"
    }
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code == 200:
        for record in response.json().get("records", []):
            record_id = record["id"]
            if record_id != new_record_id:
                requests.patch(
                    f"{url}/{record_id}",
                    headers=HEADERS,
                    json={"fields": {"Status": "pending"}}
                )

    # Now mark the new record as selected
    patch_url = f"{url}/{new_record_id}"
    payload = {"fields": {"Status": "selected"}}
    res = requests.patch(patch_url, json=payload, headers=HEADERS)
    return res.status_code == 200

def reset_segment_status(segment):
    records = fetch_segment_record(segment)
    for record in records:
        if record["fields"].get("Status") in ["selected", "skipped"]:
            record_id = record["id"]
            url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
            requests.patch(url, json={"fields": {"Status": "pending"}}, headers=HEADERS)

def fetch_pending_themes(segment):
    return [r for r in fetch_segment_record(segment) if r["fields"].get("Status") == "pending"]

def fetch_selected_theme(segment):
    records = fetch_segment_record(segment)
    return next((r for r in records if r["fields"].get("Status") == "selected"), None)

def fetch_skipped(segment):
    records = fetch_segment_record(segment)
    return next((r for r in records if r["fields"].get("Status") == "skipped"), None)

def generate_email_draft(subject, description, segment):
    prompt = build_prompt(subject, description, segment)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

def update_airtable_fields(record_id, fields):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    return requests.patch(url, json={"fields": fields}, headers=HEADERS)

def send_draft_email_to_shane(subject, draft):
    msg = MIMEText(
        f"Hi Shane,\n\nHere's the draft email for the \"{subject}\" campaign:\n\n{draft}\n\nIf this looks good, mark it as approved in the Streamlit app.\n\n– Your automated writing assistant"
    )
    msg["Subject"] = f"Draft ready for review: {subject}"
    msg["From"] = st.secrets["SMTP_USERNAME"]
    msg["To"] = st.secrets["REVIEWER_EMAIL"]

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(st.secrets["SMTP_USERNAME"], st.secrets["SMTP_PASSWORD"])
        server.sendmail(msg["From"], [msg["To"]], msg.as_string())


# --- STREAMLIT APP ---
st.set_page_config(page_title="Monthly Theme Selector", layout="wide")
st.title("📬 Monthly Email Theme Selector")

for segment in ["Pre-Retiree", "Retiree"]:
    st.markdown(f"## {segment}")
    selected = fetch_selected_theme(segment)
    skipped = fetch_skipped(segment)

    if selected:
        fields = selected["fields"]
        st.success(f"Selected theme: {fields['Subject']} – {fields['Description']}")
        
        if not fields.get("EmailDraft"):
            st.write("Click below to generate a first draft of your email.")
            if st.button(f"🪄 Generate Draft for {segment}"):
                draft = generate_email_draft(fields["Subject"], fields["Description"], segment)
                update_airtable_fields(selected["id"], {"EmailDraft": draft})
                st.rerun()
    
        if fields.get("EmailDraft"):
            with st.expander("✏️ Add additional instructions and re-generate"):
                extra_prompt = st.text_area("Additional prompt (optional):", key=f"extra_prompt_{segment}")
                if st.button(f"🔁 Re-generate with prompt for {segment}", key=f"regen_{segment}"):
                    full_prompt = build_prompt(fields["Subject"], fields["Description"], segment, extra_prompt)
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": full_prompt}],
                        temperature=0.7,
                    )
                    new_draft = response.choices[0].message.content.strip()
                    update_airtable_fields(selected["id"], {"EmailDraft": new_draft})
                    st.success("Draft regenerated with new prompt.")
                    st.rerun()
    
            draft = st.text_area("✏️ Edit your draft:", value=fields["EmailDraft"], height=300)
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"💾 Save Edits for {segment}"):
                    update_airtable_fields(selected["id"], {"EmailDraft": draft})
                    st.success("Draft saved.")
            with col2:
                if fields.get("EmailDraft") and not fields.get("DraftApproved", False):
                    if st.button(f"📤 Send to Shane for Approval for {segment}"):
                        update_airtable_fields(selected["id"], {"DraftSubmitted": True})
                        send_draft_email_to_shane(fields["Subject"], draft)
                        st.success("Draft sent to Shane for review.")
                    
            if not fields.get("DraftApproved") and st.button(f"✅ Mark as Approved for {segment}"):
                update_airtable_fields(selected["id"], {"DraftApproved": True})
                st.success("Draft marked as approved.")
    
        if st.button(f"🔄 Change Theme for {segment}"):
            reset_segment_status(segment)
            st.rerun()

    elif skipped:
        st.info("You’ve opted not to send a campaign this month.")
        if st.button(f"🔁 Change your mind for {segment}"):
            reset_segment_status(segment)
            st.rerun()

    else:
        pending = fetch_pending_themes(segment)
        if not pending:
            st.warning("No pending themes available.")
            continue

        options = {
            f"{r['fields']['Subject']} – {r['fields']['Description']}": r["id"]
            for r in pending
        }
        choice = st.radio("Select a theme:", list(options.keys()), key=f"choice_{segment}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"✅ Confirm selection for {segment}"):
                reset_segment_status(segment)
                update_status(segment, options[choice])
                st.rerun()
        with col2:
            if st.button(f"🚫 Not this month for {segment}"):
                reset_segment_status(segment)
                update_status(segment, options[choice])  # skip by reusing one of the record ids
                update_airtable_fields(options[choice], {"Status": "skipped"})
                st.rerun()

        # Show manual theme entry only when no selection has been made
        with st.expander(f"➕ Add Manual Theme for {segment}"):
            with st.form(f"manual_theme_form_{segment}"):
                subject = st.text_input("Subject Line", key=f"subject_{segment}")
                description = st.text_area("Description", key=f"desc_{segment}")
                if st.form_submit_button("💾 Save Theme"):
                    if not subject or not description:
                        st.error("Please enter both subject and description.")
                    else:
                        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
                        payload = {
                            "fields": {
                                "Segment": segment,
                                "Subject": subject,
                                "Description": description,
                                "Status": "pending",
                                "Month": get_month()
                            }
                        }
                        res = requests.post(url, json={"records": [payload]}, headers=HEADERS)
                        if res.status_code == 200:
                            st.success("Manual theme added successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to add theme: " + res.text)



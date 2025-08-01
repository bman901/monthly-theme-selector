import streamlit as st
import requests
from datetime import datetime
import pytz
from openai import OpenAI
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json

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
            f"""These readers are in their 50s or early 60s, often still working (full or part time), and juggling business or family commitments.
            They’ve done well financially but want to ensure they’re not missing anything as retirement comes into view.
            
            Focus on:
            - Reducing complexity (e.g. super accounts, offset loans, investments)
            - Knowing when/how to wind down work
            - Avoiding the cost of procrastination or false confidence (“we’re doing fine”)
            - Highlighting the value of early clarity (while choices are still wide)
            
            Avoid:
            - Pension-phase drawdown content
            - Age Pension, Centrelink, or aged care topics
            - Tone that implies they’ve already retired or are about to any minute"""
        ),
        "Retiree": (
            f"""These readers are in their 60s or early 70s and have stopped full-time work. They’re no longer building wealth—they’re using it.
            They want peace of mind, simplicity, and guidance that’s aligned with their values.
            
            Focus on:
            - Confident drawdown and income management
            - Managing market risk without panic
            - Planning for estate and family support
            - Spending without regret
            - Simplifying their financial life
            - Navigating health, longevity, or cognitive decline risk
            
            Avoid:
            - Early-stage questions like “Can we scale back work?”
            - Business exits, accumulation strategies, or super contribution rules"""
        )
    }
    base_prompt = f"""
Your job is to help a time-poor, financially successful Australian {segment.lower()} reader see something important they’ve been putting off or unsure about—without sounding alarmist or promotional.

Use the subject and theme description below as your starting point. They must shape the core insight and message of the email. Do not reinterpret or reframe them.
Subject: {subject}  
Theme description: {description}
Persona: {personas[segment]}

You are writing on behalf of Shane Hatch from Hatch Financial Planning in Logan, Queensland.
The audience includes individuals or couples with at least $1 million in investable assets (excluding their home), aged approximately 50–70.
They are financially capable, time-poor, and thinking seriously about how to approach the next stage of life with clarity and confidence.
They’re not asking “Can we retire?” but “Can we afford to say yes to the life we want?”

You are writing one plain-text email (of around 500 words) in Shane’s voice.
Do not introduce Shane—assume readers know him.
Address each email to "*|FNAME|*".

Each email must be anchored in a real tension, belief, or financial decision that people like this face.
Use the provided theme or belief - do not invent your own.

Be specific and grounded. Avoid vague concepts like “clarity is key” or “make the most of your money.” Instead, explain what clarity looks like in real terms—e.g. fewer accounts, clear timelines, known trade-offs.
Avoid soft qualifiers like “might,” “maybe,” “can help,” “could be.” Speak confidently. Use phrases like “most people,” “we often see,” or “this often means.”
Each idea should build on the one before it. Don’t just list thoughts—develop the insight.
Aim for 1–2 sentences per idea. Vary rhythm: combine punchy lines with occasional longer reflections.
Don’t summarise or conclude too early. Let the message unfold with direction and clarity.

Example beliefs:
“We’ll get serious about this later.”
“We’ve done well, so we must be on track.”
“We’ll just sell the business when the time’s right.”
“Advice is for people with more money.”

Your tone should be:
Professional, plainspoken, and clear
Confident but calm
Warm without being soft or vague
Free from jargon, complexity, or sales talk

Your structure can vary:
Start with an insight or challenge—not a story, scene, or metaphor
Sometimes use a quick example, stat, or reflection—but never as fluff
Use short, punchy sentences. Each one should deliver an idea
Wrap up with a clear, useful action or reflection (even something small)

Each email should include:
A clear point of view
One idea that removes fog or reveals something people often miss
A small, concrete takeaway—something the reader can reflect on or act on immediately
A sign off as Shane at the end of the email body (before the P.S.), saying 'Warm Regards', 'Best Wishes' or something similar
A warm, non-salesy P.S. that links to Shane’s diary
Do not include a call-to-action in the body. You may suggest a reflection or question to consider—but never tell the reader what to do. The only link or invitation should appear in the P.S.

Avoid:
Stories or characters at the start (you can use them later, but not to open)
Motivation, metaphors, or “imagine this” style hooks
Age, location, or other overly specific references
Financial product talk or technical strategies

Do not use:
Formatting (bold, italics, bullet points)
Paragraphs.
Each sentence or two must appear on its own line. Insert two hard line breaks (press Return twice) after every one or two sentences. Do not group sentences into paragraphs under any circumstances.
En dashes (–) or em dashes (—). Use standard hyphens (-) only and only when necessary.
"""
    if extra:
        base_prompt += f"\n\nAdditional instructions: {extra}"
    return base_prompt


# --- HELPERS ---
def get_month():
    brisbane = pytz.timezone("Australia/Brisbane")
    now = datetime.now(brisbane)
    return now.strftime("%B %Y")

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
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Draft ready for review: {subject}"
    msg["From"] = st.secrets["SMTP_USERNAME"]
    msg["To"] = st.secrets["REVIEWER_EMAIL"]

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <p>Hi Shane,</p>
        <p>Here's the draft email for the "<strong>{subject}</strong>" campaign:</p>
        
        <div style="border-left: 4px solid #4CAF50; background-color: #f9f9f9; padding: 16px; margin: 12px 0; font-size: 15px;">
            {draft.replace('\n', '<br>')}
        </div>
        
        <p>
            You can approve or edit this draft here:<br>
            <a href="https://hfp-monthly-theme-selector.streamlit.app/" style="color: #1a73e8;">Open the Streamlit App.</a><br>
            Or reply to this email.
        </p>
    
        <p>– Your automated writing assistant</p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(st.secrets["SMTP_USERNAME"], st.secrets["SMTP_PASSWORD"])
        server.sendmail(msg["From"], [msg["To"]], msg.as_string())

def send_approval_notification_to_ben(subject):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"✅ Approved: {subject}"
    msg["From"] = st.secrets["SMTP_USERNAME"]
    msg["To"] = st.secrets["NOTIFY_EMAIL"]

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <p>Hi Ben,</p>
        <p>The draft email for <strong>{subject}</strong> has been approved by Shane.</p>
        <p>
            You can review the final copy or continue with the next step here:<br>
            <a href="https://hfp-monthly-theme-selector.streamlit.app/" style="color: #1a73e8;">Open the Streamlit App</a>
        </p>
        <p>– Your automated writing assistant</p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(st.secrets["SMTP_USERNAME"], st.secrets["SMTP_PASSWORD"])
        server.sendmail(msg["From"], [msg["To"]], msg.as_string())

# --- MAILCHIMP LINK ---

def create_mailchimp_campaign(subject, draft, segment, preview_text=None):
    # Mailchimp config
    api_key = st.secrets["MAILCHIMP_API_KEY"]
    server_prefix = st.secrets["MAILCHIMP_SERVER_PREFIX"]
    list_id = st.secrets["MAILCHIMP_AUDIENCE_ID"]

    # Segment tag ID
    tag_id = (
        st.secrets["MAILCHIMP_TAG_ID_PRE_RETIREES"]
        if segment == "Pre-Retiree"
        else st.secrets["MAILCHIMP_TAG_ID_RETIREES"]
    )

    base_url = f"https://{server_prefix}.api.mailchimp.com/3.0"
    auth = ("anystring", api_key)  # Mailchimp uses basic auth

    # Step 1: Create campaign
    campaign_data = {
        "type": "regular",
        "recipients": {
            "list_id": list_id,
            "segment_opts": {
                "match": "any",
                "conditions": [
                    {
                        "condition_type": "StaticSegment",
                        "field": "static_segment",
                        "op": "eq",
                        "value": tag_id
                    }
                ]
            },
        },
        "settings": {
            "subject_line": subject,
            "title": f"{segment} Campaign - {subject}",
            "from_name": "Hatch Financial Planning",
            "reply_to": st.secrets["SMTP_USERNAME"],
            "auto_footer": False
        }
    }

    campaign_res = requests.post(
        f"{base_url}/campaigns",
        auth=auth,
        json=campaign_data
    )

    if campaign_res.status_code != 200:
        st.error("❌ Failed to create Mailchimp campaign.")
        st.error(campaign_res.text)
        return None

    campaign_id = campaign_res.json()["id"]

    # Step 2: Set campaign content
    content_data = {
        "plain_text": draft,
        "html": f"<html><body><p>{draft.replace(chr(10), '<br>')}</p></body></html>"
    }

    content_res = requests.put(
        f"{base_url}/campaigns/{campaign_id}/content",
        auth=auth,
        json=content_data
    )

    if content_res.status_code == 200:
        st.success("📤 Campaign created in Mailchimp!")
    else:
        st.error("❌ Failed to set campaign content.")
        st.error(content_res.text)

# --- STREAMLIT APP ---
st.set_page_config(page_title="Monthly Theme Selector", layout="wide")
st.title("📬 Monthly Email Theme Selector")

for segment in ["Pre-Retiree", "Retiree"]:
    st.markdown(f"## {segment}")
    if f"extra_prompt_{segment}" not in st.session_state:
        st.session_state[f"extra_prompt_{segment}"] = ""
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
    
        if fields.get("EmailDraft") and not fields.get("DraftApproved"):
            with st.expander("✏️ Add additional instructions and re-generate"):
                st.session_state[f"extra_prompt_{segment}"] = st.text_area(
                    "Additional prompt (optional):",
                    value=st.session_state[f"extra_prompt_{segment}"],
                    key=f"prompt_box_{segment}"
                )
                colA, colB, colC = st.columns(3)
                with colA:
                    if st.button("➕ Direct Insight", key=f"insight_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: direct insight"
                
                with colB:
                    if st.button("➕ Story", key=f"story_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: story"
                
                with colC:
                    if st.button("➕ Exercise", key=f"exercise_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: exercise"
                
                colD, colE, colF = st.columns(3)
                with colD:
                    if st.button("➕ Myth Buster", key=f"myth_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: myth buster"
                
                with colE:
                    if st.button("➕ Case Study", key=f"case_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: case study"
                
                with colF:
                    if st.button("➕ Q&A", key=f"qa_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: Q&A"

                if st.button(f"🔁 Re-generate with prompt for {segment}", key=f"regen_{segment}"):
                    full_prompt = build_prompt(
                        fields["Subject"],
                        fields["Description"],
                        segment,
                        st.session_state[f"extra_prompt_{segment}"]
                    )
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": full_prompt}],
                        temperature=0.7,
                    )
                    new_draft = response.choices[0].message.content.strip()
                    update_airtable_fields(selected["id"], {"EmailDraft": new_draft})
                    st.success("Draft regenerated with new prompt.")
                    st.rerun()
    
        if fields.get("DraftApproved"):
            st.success("✅ This draft has been approved and is ready to send.")
            st.text_area(
                label="✉️ Final Draft (read-only)",
                value=fields["EmailDraft"],
                height=300,
                disabled=True
            )
            if st.button(f"✏️ Edit Draft Again for {segment}", key=f"editagain_{segment}"):
                update_airtable_fields(selected["id"], {"DraftApproved": False})
                st.rerun()
            if st.button(f"📤 Push to Mailchimp for {segment}", key=f"mailchimp_{segment}"):
                create_mailchimp_campaign(fields["Subject"], fields["EmailDraft"], segment)
        
        else:
            draft = st.text_area("✏️ Edit your draft:", value=fields.get("EmailDraft", ""), height=300, key=f"edit_draft_{segment}")

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(f"💾 Save Edits for {segment}", key=f"save_{segment}"):
                    update_airtable_fields(selected["id"], {"EmailDraft": draft})
                    st.success("Draft saved.")
            with col2:
                if st.button(f"🔄 Change Theme for {segment}"):
                    reset_segment_status(segment)
                    st.rerun()
            with col3:
                if fields.get("EmailDraft") and not fields.get("DraftApproved", False):
                    if st.button(f"📤 Send to Shane for Approval for {segment}",key=f"send_{segment}"):
                        update_airtable_fields(selected["id"], {"EmailDraft": draft})
                        update_airtable_fields(selected["id"], {"DraftSubmitted": True})
                        send_draft_email_to_shane(fields["Subject"], draft)
                        st.success("Draft sent to Shane for review.")           
                
        if not fields.get("DraftApproved") and st.button(f"✅ Mark as Approved for {segment}"):
            update_airtable_fields(selected["id"], {"DraftApproved": True})
            send_approval_notification_to_ben(fields["Subject"])
            st.success("Draft marked as approved and notification sent.")

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



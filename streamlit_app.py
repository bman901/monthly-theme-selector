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
        "These readers are in their 50s or early 60s and still working—often juggling business, work, or family commitments.\n"
        "They’ve done well financially but want to ensure they’re not missing anything as retirement comes into view.\n\n"
        "Focus on:\n"
        "- Reducing complexity (super, loans, investments)\n"
        "- Knowing when/how to wind down work\n"
        "- Avoiding the cost of procrastination or false confidence ('we’re doing fine')\n"
        "- Highlighting the value of early clarity (while choices are still wide)\n\n"
        "Avoid:\n"
        "- Pension-phase drawdown or Centrelink topics\n"
        "- Tone that implies they’re already retired"
    ),
    "Retiree": (
        "These readers are in their 60s or early 70s and no longer working full time. They’re using—not building—their wealth.\n"
        "They want peace of mind, simplicity, and financial guidance aligned with their values.\n\n"
        "Focus on:\n"
        "- Confident drawdown and income management\n"
        "- Managing market risk without panic\n"
        "- Planning for estate and family support\n"
        "- Simplifying their financial life\n"
        "- Navigating health, longevity, or cognitive decline risks\n\n"
        "Avoid:\n"
        "- Early-stage questions like 'Can we scale back work?'\n"
        "- Business exits, accumulation strategies, or contribution rules"
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
Start each email with "Hi *|FNAME|*" including the asterisks.
Use Australian spelling consistently throughout.
Avoid Americanisms such as “realize,” “optimize,” or “calendar.”
Write naturally for an Australian reader.

Each email must be anchored in a real tension, belief, or financial decision that people like this face.
Use the provided theme or belief - do not invent your own.
The email must confront the belief or tension embedded in the theme or description.
Do not soften the belief with motivational phrasing or by shifting focus to general positives.
Name the consequence or missed opportunity that results from avoiding the core decision.
Then build toward one concrete, grounded insight that helps shift perspective.

Examples of strong belief tension openers:
“Most people don’t realise how much money they leave unstructured.”
“You can be financially secure and still feel unprepared.”
“We often meet people who’ve done everything right—but still hesitate.”
These aren’t harsh—but they’re sharp. They start with truth, not fluff.

Be specific and grounded. Avoid vague concepts like “clarity is key” or “make the most of your money.” Instead, explain what clarity looks like in real terms—e.g. fewer accounts, clear timelines, known trade-offs.
Avoid soft qualifiers like “might,” “maybe,” “can help,” “could be.” Speak confidently. Use phrases like “most people,” “we often see,” or “this often means.”
Each idea should build on the one before it. Don’t just list thoughts—develop the insight.
Use friction and consequence. Show what inaction really costs—whether it’s missed years, poor timing, or hidden complexity.
Be explicit about what inaction can cost. Use concrete consequences: earning extra years, missing long-term strategies, overlooked tax or flexibility opportunities. Name an outcome people might regret—not just “missed opportunities.”
Avoid circular phrasing. Each sentence should move the reader toward clarity.
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
Open with a sharp truth or tension—something a time-poor, smart reader would instantly recognise as real and relevant. Avoid soft openings like “You’ve worked hard.”
The goal is to disarm quietly—not to provoke or preach.
Sometimes use a quick example, stat, or reflection—but never as fluff
Avoid overused phrases or generic GPT-style lines (e.g. “clarity is key”, “say yes to what you want”, “it’s not just about the numbers”). These sound polished but lack substance.
Instead, use plain, specific language grounded in real financial experiences or decision points.
Make every sentence earn its place.
Avoid filler, clichés, or soft statements like “clarity is key” or “you deserve peace of mind.”
Prefer short, punchy sentences as much as possible, but you can add longer sentences where it adds value and as a point of difference.
Every line should deliver an insight, build tension, or offer a practical shift in thinking.
Don’t repeat phrases unless it’s intentional for rhythm or contrast.
Do not include hypothetical phrases like “Imagine knowing…” or “It can feel like…” These prompt fanciful thinking. Instead, stick to real experiences or practical realities commonly observed among people like this.

Wrap up with a clear, useful takeaway. This could be a reflection or small action—something the reader can do or think about immediately.
Include one specific micro-action—not a general prompt. For example:
“Pick one super account you haven’t reviewed in over a year and ask: does this still serve your goals?”
“List every active account you have—if it’s more than five, it’s time to simplify.”

Then, before the sign-off, add one sharp sentence that reconnects the reflection or action to a real-life consequence of inaction. 
This must highlight what’s at stake—not by summarising, but by sharpening the tension.
Example:
“Because what’s unclear today often becomes the thing that holds you back tomorrow.”
Avoid soft fades or vague conclusions. Make sure the final sentence before the sign-off delivers a clear insight or consequence.

Each email should include:
A clear point of view
One idea that removes fog or reveals something people often miss
A small, concrete takeaway—something the reader can reflect on or act on immediately
A sign off as Shane at the end of the email body (before the P.S.), saying 'Warm Regards', 'Best Wishes' or something similar
A warm, non-salesy P.S. that links to Shane’s diary
The P.S. must stay warm and low-key.
Do not use promotional phrases like “gain clarity,” “plan your future,” or “secure your retirement.”
Just link simply and naturally to Shane’s diary, as if inviting a casual follow-up.
Do not include a call-to-action in the body. You may suggest a reflection or question to consider—but never tell the reader what to do. The only link or invitation should appear in the P.S.

Avoid:
Stories or characters at the start (you can use them later, but not to open)
Motivation, metaphors, or “imagine this” style hooks
Age, location, or other overly specific references
Financial product talk or technical strategies
GPT-style phrasing like “gain clarity and confidence,” “imagine the freedom,” or “unlock your potential.”
These sound polished but generic and erode trust.
Use grounded, plainspoken language that reflects real financial experiences or trade-offs.
Circular phrasing. Each sentence should move the reader toward clarity.

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
    api_key = st.secrets["MAILCHIMP_API_KEY"]
    server_prefix = st.secrets["MAILCHIMP_SERVER_PREFIX"]
    audience_id = st.secrets["MAILCHIMP_AUDIENCE_ID"]

    tag_id = (
        st.secrets["MAILCHIMP_TAG_ID_PRE_RETIREES"]
        if segment == "Pre-Retiree"
        else st.secrets["MAILCHIMP_TAG_ID_RETIREES"]
    )

    base_url = f"https://{server_prefix}.api.mailchimp.com/3.0"
    auth = ("anystring", api_key)

    campaign_data = {
        "type": "regular",
        "recipients": {
            "list_id": audience_id,
            "segment_opts": {
                "saved_segment_id": tag_id
            }
        },
        "settings": {
            "subject_line": subject,
            "title": f"{segment} Campaign - {subject}",
            "from_name": "Hatch Financial Planning",
            "reply_to": st.secrets["SMTP_USERNAME"],
            "auto_footer": False
        }
    }

    campaign_res = requests.post(f"{base_url}/campaigns", auth=auth, json=campaign_data)
    if campaign_res.status_code != 200:
        st.error("❌ Failed to create campaign.")
        st.error(campaign_res.text)
        return None
    campaign_id = campaign_res.json()["id"]

    content = {
        "plain_text": draft,
        "html": f"<html><body><p>{draft.replace(chr(10), '<br>')}</p></body></html>"
    }

    content_res = requests.put(f"{base_url}/campaigns/{campaign_id}/content", auth=auth, json=content)
    if content_res.status_code == 200:
        st.success(f"✅ Campaign created (not sent), ID: {campaign_id}")
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
                colA, colB, colC, colD = st.columns(4)
                with colA:
                    if st.button("➕ Direct Insight", key=f"insight_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: direct insight"
                        st.rerun()
                
                with colB:
                    if st.button("➕ Story", key=f"story_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: story"
                        st.rerun()
                
                with colC:
                    if st.button("➕ Exercise", key=f"exercise_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: exercise"
                        st.rerun()

                with colD:
                    if st.button("➕ Recent Study", key=f"study_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += """\nReference a recent study.
Do not fabricate data or statistics. Only include references to studies or findings that are plausible and widely reported.
Avoid citing exact figures (e.g. “63%”) unless you are confident they are accurate and well-established.
Prefer general phrasing such as “A recent study found…” or “Surveys often show…” Do not mention the reader’s demographic, age, or personal situation—keep the reference broad and relevant to the theme. If you can’t confidently cite a known study, imply a trend without stating specific details."""
                        st.rerun()
                
                colE, colF, colG, colH = st.columns(4)
                with colE:
                    if st.button("➕ Myth Buster", key=f"myth_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: myth buster"
                        st.rerun()
                
                with colF:
                    if st.button("➕ Case Study", key=f"case_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: case study"
                        st.rerun()
                
                with colG:
                    if st.button("➕ Q&A", key=f"qa_{segment}"):
                        st.session_state[f"extra_prompt_{segment}"] += "\nFormat: Q&A"
                        st.rerun()

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



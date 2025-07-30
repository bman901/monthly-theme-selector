import streamlit as st
import requests
from datetime import datetime
import openai

openai.api_key = st.secrets["OPENAI_API_KEY"]

# Airtable config
AIRTABLE_PAT = st.secrets["AIRTABLE_PAT"]
AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
AIRTABLE_TABLE_NAME = "MonthlyThemes"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_PAT}",
    "Content-Type": "application/json"
}

# Airtable fetch
def fetch_pending_themes(segment):
    this_month = datetime.now().strftime("%B %Y")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    params = {
        "filterByFormula": f"AND(Segment = '{segment}', Status = 'pending', Month = '{this_month}')",
        "pageSize": 50
    }
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        st.error(f"Error fetching {segment} themes: {response.text}")
        return []
    return response.json().get("records", [])

# Airtable update
def update_status(record_id):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    data = {"fields": {"Status": "selected"}}
    response = requests.patch(url, json=data, headers=HEADERS)
    return response.status_code == 200

# Page setup
st.set_page_config(page_title="Theme Selector", layout="wide")
st.title("📬 Monthly Email Theme Selector")

# --- THEME SELECTORS ---
for segment in ["Pre-Retiree", "Retiree"]:
    st.header(segment)
    records = fetch_pending_themes(segment)

    if not records:
        st.info("No pending themes for this segment.")
        continue

    options = {
        f"{r['fields']['Subject']} – {r['fields']['Description']}": r['id']
        for r in records
    }

    choice = st.radio(
        f"Select a theme for {segment}:", list(options.keys()), key=segment)

    if st.button(f"✅ Confirm selection for {segment}", key=f"{segment}_confirm"):
        selected_id = options[choice]
        if update_status(selected_id):
            st.success("Selection saved!")
        else:
            st.error("Failed to update Airtable.")

# --- MANUAL ENTRY ---
st.markdown("---")
st.header("✍️ Manually Create a Theme")

with st.form("manual_theme_form"):
    manual_segment = st.selectbox("Segment", ["Pre-Retiree", "Retiree"])
    subject = st.text_input("Subject Line")
    description = st.text_area("Description (1–2 sentences)")
    submitted = st.form_submit_button("💾 Save Theme")

    if submitted:
        if not subject or not description:
            st.error("Please complete both the subject and description.")
        else:
            url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
            payload = {
                "fields": {
                    "Segment": manual_segment,
                    "Subject": subject,
                    "Description": description,
                    "Status": "pending",
                    "Month": datetime.now().strftime("%B %Y")
                }
            }
            res = requests.post(url, json={"records": [payload]}, headers=HEADERS)
            if res.status_code == 200:
                st.success("🎉 Theme saved successfully!")
                st.rerun()  # Auto-refresh to show new theme
            else:
                st.error(f"⚠️ Failed to save theme: {res.text}")

# --- GENERATE EMAILS ---

# Define personas
personas = {
    "Pre-Retiree": (
        "Paul and Lisa Harrington are in their late 50s in South East QLD. "
        "They’re financially comfortable but time-poor. "
        "They value clarity, simplicity, and confidence about the future. "
    ),
    "Retiree": (
        "Alan and Margaret Rowe are in their mid to late 60s in South East QLD. "
        "They're thoughtful, detail-focused, and value peace of mind. "
    )
}

st.markdown("---")
st.header("📝 Generate and Review Email Drafts")

for segment in ["Pre-Retiree", "Retiree"]:
    selected = fetch_pending_themes(segment)
    selected = [r for r in selected if r["fields"].get("Status") == "selected"]

    if not selected:
        st.info(f"No selected theme for {segment} yet.")
        continue

    record = selected[0]  # Only one selected theme per segment
    fields = record["fields"]
    subject = fields["Subject"]
    description = fields["Description"]
    draft = fields.get("EmailDraft", "")
    approved = fields.get("DraftApproved", False)
    record_id = record["id"]

    st.subheader(f"{segment}: {subject}")
    st.caption(description)

    if not draft:
        if st.button(f"🪄 Generate Email Draft for {segment}"):
            prompt = (
                f"Write a marketing email suitable for Australian {segment.lower()} clients. "
                f"Subject: {subject}\n"
                f"Theme description: {description}\n"
                f"Persona: {personas[segment]}\n\n"
                f"The email should be informative, conversational, and have a clear 'book a call' style CTA. "
                f"Try to deliver value and actionable items, don't make it salesy "
                f"Use Australian English. Do not use em or en dashes — use normal hyphens (-) only and sparingly so."
            )
            with st.spinner("Generating email..."):
                response = openai.ChatCompletion.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                )
                email_text = response.choices[0].message.content.strip()

                # Update Airtable
                url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
                payload = {"fields": {"EmailDraft": email_text}}
                res = requests.patch(url, json=payload, headers=HEADERS)
                if res.status_code == 200:
                    st.success("✅ Email draft saved.")
                    st.rerun()
                else:
                    st.error("❌ Failed to save draft to Airtable.")

    else:
        edited_draft = st.text_area("✏️ Edit the draft below", value=draft, height=300, key=f"edit_{segment}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"💾 Save Edits for {segment}"):
                url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
                payload = {"fields": {"EmailDraft": edited_draft}}
                res = requests.patch(url, json=payload, headers=HEADERS)
                if res.status_code == 200:
                    st.success("Draft updated.")
                    st.rerun()
        with col2:
            if not approved and st.button(f"✅ Mark as Approved for {segment}"):
                url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
                payload = {"fields": {"DraftApproved": True}}
                res = requests.patch(url, json=payload, headers=HEADERS)
                if res.status_code == 200:
                    st.success("Marked as approved.")
                    st.rerun()

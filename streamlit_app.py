import streamlit as st
import requests
from datetime import datetime

# Load secrets securely from Streamlit Cloud
AIRTABLE_PAT = st.secrets["AIRTABLE_PAT"]
AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]
AIRTABLE_TABLE_NAME = "MonthlyThemes"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_PAT}",
    "Content-Type": "application/json"
}

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

def update_status(record_id):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    data = {
        "fields": {
            "Status": "selected"
        }
    }
    response = requests.patch(url, json=data, headers=HEADERS)
    return response.status_code == 200

st.set_page_config(page_title="Theme Selector", layout="wide")
st.title("📬 Monthly Email Theme Selector")

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

    choice = st.radio(f"Select a theme for {segment}:", list(options.keys()), key=segment)

    if st.button(f"✅ Confirm selection for {segment}", key=f"{segment}_confirm"):
        selected_id = options[choice]
        if update_status(selected_id):
            st.success("Selection saved!")
        else:
            st.error("Failed to update Airtable.")

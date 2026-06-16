import anthropic
import smtplib
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── Config (set these as GitHub Secrets) ──────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SENDER_EMAIL      = os.environ["SENDER_EMAIL"]       # Gmail address you send FROM
SENDER_PASSWORD   = os.environ["SENDER_PASSWORD"]    # Gmail App Password (not your login password)
RECIPIENT_EMAIL   = os.environ["RECIPIENT_EMAIL"]    # nicole@experienceolympia.com
# ──────────────────────────────────────────────────────────────────────────────

def fetch_digest():
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today = datetime.now().strftime("%A, %B %-d, %Y")

    prompt = (
        f"Today is {today}. Search the web for business news in Thurston County, "
        "Washington (Olympia, Lacey, Tumwater, Yelm, and surrounding areas) from "
        "the past 24 hours. Find: new business openings, closures, new menu items, "
        "specials, renovations, or expansions. "
        "Return ONLY a raw JSON object — no markdown, no backticks, no explanation — "
        "in this exact structure: "
        '{\"openings\":[{\"name\":\"...\",\"description\":\"...\",\"source\":\"...\"}],'
        '\"closures\":[{\"name\":\"...\",\"description\":\"...\",\"source\":\"...\"}],'
        '\"new_offerings\":[{\"name\":\"...\",\"description\":\"...\",\"source\":\"...\"}],'
        '\"other\":[{\"name\":\"...\",\"description\":\"...\",\"source\":\"...\"}]} '
        "Keep descriptions to 1-2 sentences. Use an empty array if no items in a category."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    raw = "".join(b.text for b in response.content if hasattr(b, "text"))
    # Strip any accidental markdown fences
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


def build_html(data, today):
    def section(title, items, empty_msg):
        if not items:
            return f"<h3>{title}</h3><p style='color:#888'>{empty_msg}</p>"
        rows = "".join(
            f"<div style='margin-bottom:12px'>"
            f"<strong>{i.get('name','')}</strong> — {i.get('description','')}"
            f"<br><span style='font-size:12px;color:#888'>via {i.get('source','')}</span>"
            f"</div>"
            for i in items
        )
        return f"<h3>{title}</h3>{rows}"

    body = f"""
    <div style='font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px'>
      <h2 style='margin-bottom:4px'>Thurston County Business Digest</h2>
      <p style='color:#888;margin-top:0'>{today}</p>
      <hr style='border:none;border-top:1px solid #eee;margin:16px 0'>
      {section("New Openings", data.get("openings", []), "No new openings today.")}
      <hr style='border:none;border-top:1px solid #eee;margin:16px 0'>
      {section("Closures", data.get("closures", []), "No closures today.")}
      <hr style='border:none;border-top:1px solid #eee;margin:16px 0'>
      {section("New Offerings &amp; Specials", data.get("new_offerings", []), "Nothing new today.")}
      <hr style='border:none;border-top:1px solid #eee;margin:16px 0'>
      {section("Other Business News", data.get("other", []), "Nothing else today.")}
      <hr style='border:none;border-top:1px solid #eee;margin:16px 0'>
      <p style='font-size:12px;color:#aaa'>Powered by Claude + web search</p>
    </div>
    """
    return body


def send_email(html, today):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Thurston County Business Digest — {today}"
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print(f"Digest sent to {RECIPIENT_EMAIL}")


if __name__ == "__main__":
    today = datetime.now().strftime("%A, %B %-d, %Y")
    print(f"Fetching digest for {today}...")
    data = fetch_digest()
    html = build_html(data, today)
    send_email(html, today)

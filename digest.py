import anthropic
import smtplib
import json
import re
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SENDER_EMAIL      = os.environ["SENDER_EMAIL"]
SENDER_PASSWORD   = os.environ["SENDER_PASSWORD"]
RECIPIENT_EMAIL   = os.environ["RECIPIENT_EMAIL"]

def fetch_digest():
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today = datetime.now().strftime("%A, %B %-d, %Y")

    # Shorter prompt = fewer input tokens = less likely to hit rate limit
    prompt = (
        f"Today is {today}. Search for recent business news in Thurston County WA "
        "(Olympia, Lacey, Tumwater, Yelm). Find: openings, closures, new menus, specials. "
        "Reply with ONLY this JSON, no extra text:\n"
        '{"openings":[{"name":"","description":"","source":""}],'
        '"closures":[{"name":"","description":"","source":""}],'
        '"new_offerings":[{"name":"","description":"","source":""}],'
        '"other":[{"name":"","description":"","source":""}]}'
    )

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": prompt}]
            )
            break
        except anthropic.RateLimitError:
            if attempt < 2:
                print(f"Rate limited, waiting 30s before retry {attempt + 2}/3...")
                time.sleep(30)
            else:
                raise

    raw = ""
    for block in response.content:
        if hasattr(block, "text") and block.text:
            raw += block.text

    print("Raw response:", raw[:300])

    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in response: {raw[:300]}")

    return json.loads(match.group())


def build_html(data, today):
    def section(title, items, empty_msg):
        if not items:
            return f"<h3 style='color:#333'>{title}</h3><p style='color:#888'>{empty_msg}</p>"
        rows = "".join(
            f"<div style='margin-bottom:12px'>"
            f"<strong>{i.get('name','')}</strong> — {i.get('description','')}"
            f"<br><span style='font-size:12px;color:#888'>via {i.get('source','')}</span>"
            f"</div>"
            for i in items
        )
        return f"<h3 style='color:#333'>{title}</h3>{rows}"

    return f"""
    <div style='font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px'>
      <h2 style='margin-bottom:4px;color:#111'>Thurston County Business Digest</h2>
      <p style='color:#888;margin-top:0'>{today}</p>
      <hr style='border:none;border-top:1px solid #eee;margin:16px 0'>
      {section("🟢 New Openings", data.get("openings", []), "No new openings today.")}
      <hr style='border:none;border-top:1px solid #eee;margin:16px 0'>
      {section("🔴 Closures", data.get("closures", []), "No closures today.")}
      <hr style='border:none;border-top:1px solid #eee;margin:16px 0'>
      {section("✨ New Offerings & Specials", data.get("new_offerings", []), "Nothing new today.")}
      <hr style='border:none;border-top:1px solid #eee;margin:16px 0'>
      {section("📰 Other Business News", data.get("other", []), "Nothing else today.")}
      <hr style='border:none;border-top:1px solid #eee;margin:16px 0'>
      <p style='font-size:12px;color:#aaa'>Powered by Claude + web search</p>
    </div>
    """


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

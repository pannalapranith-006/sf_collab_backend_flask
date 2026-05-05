from app.services.ai_core.ai_service import AIService


TARGET_CTA = {
    "clients": "Would you be open to a quick conversation?",
    "investors": "Would you be open to a short intro call?",
    "partners": "Would you be interested in exploring a partnership?",
    "employees": "Would you be interested in learning more?"
}

def generate_outreach_draft(campaign, user):
    

    # Lazily create the Groq client only when this function is called
    

    prompt = f"""
Generate a professional cold outreach email.

Context:
Sender: {user.first_name} {user.last_name}
Target type: {campaign.target_type}
Campaign description: {campaign.description}

Rules:
- Email must be honest and professional
- Do not impersonate other companies
- Do not request passwords, payments, or sensitive data
- Do not use deceptive marketing
- No emojis
- Plain text
- Friendly and concise

Output format strictly:

Subject:
<subject>

Body:
<body>
"""


    result = AIService.generate(
    feature="outreach_email",
    user_input=prompt,
    temperature=0.4,
    max_tokens=500
)

    text = result.get("response", "").strip()
    if detect_phishing(text):
        raise ValueError("Generated email appears unsafe")

    subject = ""
    body = ""

    if "Subject:" in text and "Body:" in text:
        subject = text.split("Subject:")[1].split("Body:")[0].strip()
        body = text.split("Body:")[1].strip()
    else:
        subject = "Quick introduction"
        body = text

    return subject, body


def detect_phishing(text):
    patterns = [
        "verify your account",
        "send payment",
        "crypto transfer",
        "urgent payment required",
        "click this secure link",
        "password confirmation"
    ]

    t = text.lower()

    for p in patterns:
        if p in t:
            return True

    return False


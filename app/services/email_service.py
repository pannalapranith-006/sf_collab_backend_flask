import smtplib
import os
from app.utils.email_templates.email_templates import templates
# import resend
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import os
from email.mime.base import MIMEBase
from email import encoders

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, "static", "logo.png")

# resend.api_key = os.getenv("RESEND_API_KEY")

class EmailService:

  def __init__(self):
    self.smtp_server = os.getenv('MAIL_SERVER')
    self.use_tls = os.getenv('MAIL_USE_TLS') == 'True'
    self.port = int(os.getenv('MAIL_PORT'))
    self.username = os.getenv('MAIL_USERNAME')
    self.password = os.getenv('MAIL_PASSWORD')
    self.default_sender = os.getenv('MAIL_DEFAULT_SENDER')    

  def send_email_verification_code(self, user, code):
    brand_name = os.getenv("BRAND_NAME", "SFCollab")
    subject = f"{brand_name}: Your Verification Code"
    body = templates.get("verification_code_email")(
      data={
        "user": {
          "name": f"{user.first_name} {user.last_name}",
          "email": user.email
        },
        "metadata": {
          "verification_code": code
        }
      },
      see_email_template=False
    )
    self.send_email(user.email, subject, body)
    print(f"Sent verification code email to {user.email}")

  def _connect(self):
        server = smtplib.SMTP(self.smtp_server, self.port)
        if self.use_tls:
            server.starttls()
        server.login(self.username, self.password)
        return server
  def send_email(self, recipient, subject, body, attachments=None):
    is_staging = os.getenv('FLASK_ENV', 'development') != 'production'
    
    if is_staging:
        if not subject.startswith('[STAGING]'):
            subject = f"[STAGING] {subject}"
        from_name = "SFCollab (Staging)"
    else:
        from_name = "SFCollab"

    server = self._connect()
    try:
      from_addr = f"{from_name} <{self.default_sender}>"
      to_addr = recipient
      msg = MIMEMultipart("related")
      msg["From"] = from_addr
      msg["To"] = to_addr
      msg["Subject"] = subject

      # HTML part
      msg.attach(MIMEText(body, "html"))

      # Attach image
      with open(LOGO_PATH, "rb") as f:
          img = MIMEImage(f.read())
          img.add_header("Content-ID", "<logo@sf>")
          img.add_header("Content-Disposition", "inline", filename="logo.png")
          msg.attach(img)

      # Attach additional files
      if attachments is not None:
          for attachment in attachments:
            print(attachment)
            path = attachment["path"]
            filename = attachment["name"]

            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=filename
                )
                msg.attach(part)


      server.sendmail(from_addr, to_addr, msg.as_string())
      print("Email sent:", recipient)
    finally:
      server.quit()
# from app.services.email_service import EmailService
# from app.utils.email_templates.email_templates import templates
# email_service = EmailService()
# verification_code_email_template = templates.get("verification_code_email")
# email_service.send_email(
#   recipient="GomezSilvaIvan@gmail.com",
#   subject="Verify Your Email Address",
#   body=verification_code_email_template(
#     data={
#       "user": {
#         "name": "Ivan",
#         "email": "GomezSilvaIvan@gmail.com"
#       },
#       "metadata": {
#         "verification_code": "123456"
#       }
#     },
#     see_email_template=False
#   )
# )
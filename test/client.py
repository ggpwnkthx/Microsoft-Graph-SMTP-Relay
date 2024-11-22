from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
import logging, os, smtplib

# Set the logging level to DEBUG for verbose output
logging.basicConfig(level=logging.DEBUG)

# Load environment variables from a .env file if SMTP_RELAY_HOSTNAME is not set
if not os.environ.get("SMTP_RELAY_HOSTNAME"):
    from dotenv import load_dotenv

    load_dotenv()

# Email server configuration from environment variables or defaults
smtp_server = (
    "localhost"
    if os.environ["SMTP_RELAY_HOSTNAME"] == "0.0.0.0"
    else os.environ["SMTP_RELAY_HOSTNAME"]
)
smtp_port = int(os.environ.get("SMTP_RELAY_PORT", 25))
smtp_user = "your-email@example.com"  # This should be replaced with a real username
smtp_password = "your-password"  # This should be replaced with a real password

# Create a MIMEMultipart message object for an email with mixed content (HTML and image)
msg = MIMEMultipart("related")
msg["Subject"] = "Email with HTML and Embedded Image"
msg["From"] = os.environ.get("TEST_FROM_ADDRESS", "me@company.com")
msg["To"] = os.environ.get("TEST_TO_ADDRESS", "me@company.com")
msg.preamble = "This is a multi-part message in MIME format."

# HTML version of the email body
html = """\
<html>
  <head></head>
  <body>
    <p>Hi!<br>
       This is just a test email that showcases both HTML and embedded attachments.<br>
    </p>
    <img src="cid:image1">
  </body>
</html>
"""
# Attach the HTML content to the email
msg.attach(MIMEText(html, "html"))

# Open the image file to be embedded and attach it to the email
with open("test/image.jpg", "rb") as img:
    mime_image = MIMEImage(img.read())
    mime_image.add_header("Content-ID", "<image1>")
    # Inline content disposition allows the image to be displayed within the email body
    mime_image.add_header("Content-Disposition", "inline", filename="image.jpg")
    msg.attach(mime_image)

# Open the PDF file and attach it
with open("test/doc.pdf", "rb") as pdf_file:
    mime_pdf = MIMEApplication(pdf_file.read(), _subtype="pdf")
    mime_pdf.add_header("Content-Disposition", "attachment", filename="doc.pdf")
    msg.attach(mime_pdf)

# Log the attempt to connect to the SMTP server
logging.info(f"Attempting to connect to SMTP service at {smtp_server}:{smtp_port}")

# Connect to the SMTP server, authenticate, and send the email
with smtplib.SMTP(smtp_server, smtp_port) as server:
    server.login(smtp_user, smtp_password)
    server.sendmail(msg["From"], msg["To"], msg.as_string())

# Confirmation message after sending the email
print("Email sent!")

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import logging, os, smtplib

logging.basicConfig(level=logging.DEBUG)

if not os.environ.get("SMTP_RELAY_HOSTNAME"):
    from dotenv import load_dotenv
    load_dotenv()
    
# Email server configuration
smtp_server = 'localhost' if os.environ["SMTP_RELAY_HOSTNAME"] == "0.0.0.0" else os.environ["SMTP_RELAY_HOSTNAME"]
smtp_port = int(os.environ.get("SMTP_RELAY_PORT", 25))
smtp_user = 'your-email@example.com'
smtp_password = 'your-password'

# Sender and recipient
from_email = 'isaac@esquireadvertising.com'
to_email = 'ibjessup@gmail.com'

# Create message container
msg = MIMEMultipart('related')
msg['Subject'] = 'Email with HTML and Embedded Image'
msg['From'] = from_email
msg['To'] = to_email
msg.preamble = 'This is a multi-part message in MIME format.'

# Create the body of the message (a HTML version).
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

# Record the MIME types.
msg.attach(MIMEText(html, 'html'))

# Attach image
with open('image.jpg', 'rb') as img:
    mime_image = MIMEImage(img.read())
    mime_image.add_header('Content-ID', '<image1>')
    mime_image.add_header('Content-Disposition', 'inline', filename='image.jpg')  # Specify content disposition as inline
    msg.attach(mime_image)

# Send the email
logging.info("Attempting to connect to SMTP service at {}:{}".format(smtp_server, smtp_port))
with smtplib.SMTP(smtp_server, smtp_port) as server:
    server.login(smtp_user, smtp_password)
    server.sendmail(from_email, to_email, msg.as_string())

print("Email sent!")
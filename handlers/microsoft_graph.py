from .auth_all import AllowAnyLOGIN
from aiosmtpd.smtp import SMTP, Session, Envelope
from email.parser import Parser
from msal import ConfidentialClientApplication, TokenCache
from typing import List
import aiohttp, base64, logging, os, uuid

if not os.environ.get("CLIENT_ID"):
    from dotenv import load_dotenv
    load_dotenv()

class MicrosoftGraphHandler(AllowAnyLOGIN):
    def __init__(self):
        self.app = ConfidentialClientApplication(
            client_id=os.environ["CLIENT_ID"],
            client_credential=os.environ["CLIENT_SECRET"],
            authority=os.environ["AUTHORITY"],
            token_cache=TokenCache(),
        )

    async def handle_DATA(self, server: SMTP, session: Session, envelope: Envelope):
        email = Parser().parsestr(envelope.content.decode("utf-8"))
        attachments = []
        body_content = "" # Default body content
        content_type = "text"  # Default content type
        
        if os.environ.get("LOG_LEVEL", "") == "DEBUG":
            with open(f"/usr/src/app/debug/{uuid.uuid4().hex}.html", "wb") as f:
                f.write(envelope.content)

        # Process multipart emails to extract body and attachments
        if email.is_multipart():
            for part in email.walk():
                if part.get_content_maintype() == "multipart":
                    continue  # Skip multipart container
                content_disposition = part.get("Content-Disposition", None)
                if (
                    part.get_content_type() in ["text/plain", "text/html"]
                    and not content_disposition
                ):
                    # Extract email body content
                    body_content = part.get_payload(decode=True).decode("utf-8")
                    content_type = (
                        "html" if part.get_content_type() == "text/html" else "text"
                    )
                elif content_disposition:
                    # Process and encode attachments
                    file_data = part.get_payload(decode=True)
                    base64_encoded = base64.b64encode(file_data).decode("utf-8")
                    attachment = {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": part.get_filename(),
                        "contentType": part.get_content_type(),
                        "contentBytes": base64_encoded,
                    }
                    if "inline" in content_disposition:
                        attachment["isInline"] = True
                        # Optionally, set a content ID or use the filename as a reference in the HTML
                        # Note: Graph API does not directly use Content-ID like traditional email systems
                        attachment["contentId"] = part.get('Content-ID', '').strip('<>').replace('@mydomain.com', '')
                    attachments.append(attachment)
        else:
            body_content = email.get_payload(decode=True).decode("utf-8")
            content_type = "html" if email.get_content_type() == "text/html" else "text"

        # Construct the request payload for sending the email via Microsoft Graph API
        send = {
            "url": f"https://graph.microsoft.com/v1.0/users/{envelope.mail_from}/sendMail",
            "headers": {
                "Authorization": "Bearer "
                + self.app.acquire_token_for_client(scopes=[".default"])["access_token"]
            },
            "json": {
                "message": {
                    "subject": email["Subject"],
                    "body": {"contentType": content_type, "content": body_content},
                    "toRecipients": [
                        {"emailAddress": {"address": addr}}
                        for addr in email.get_all("To", [])
                    ],
                    "ccRecipients": [
                        {"emailAddress": {"address": addr}}
                        for addr in email.get_all("Cc", [])
                    ],
                    "bccRecipients": [
                        {"emailAddress": {"address": addr}}
                        for addr in email.get_all("Bcc", [])
                    ],
                    "attachments": attachments,
                },
                "saveToSentItems": "false",
            },
        }

        # Log the send request for debugging
        logging.debug(send)

        # Send the email through Microsoft Graph API
        async with aiohttp.ClientSession() as session:
            async with session.post(**send) as response:
                if response.status != 202:
                    return await response.text()
        return "250 Message accepted for delivery"

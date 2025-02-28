from .auth_all import AllowAnyLOGIN
from aiosmtpd.smtp import SMTP, Session, Envelope
from email.header import decode_header, make_header
from email.message import Message
from email.parser import Parser
from email.utils import collapse_rfc2231_value, getaddresses
from msal import ConfidentialClientApplication, TokenCache
import aiohttp
import base64
import logging
import os
import uuid

# Ensure environment variables are loaded, for example, from a .env file
if not os.environ.get("CLIENT_ID"):
    from dotenv import load_dotenv

    load_dotenv()


def get_attachment_filename(part: Message):
    # Try to get the filename from the Content-Disposition header
    filename = part.get_filename(part.get_param("name"))
    if filename:
        # Decode RFC 2231 and RFC 2047 encodings
        filename = collapse_rfc2231_value(filename)
        filename = str(make_header(decode_header(filename)))
        return filename

    # If all else fails, return a UUID
    return str(uuid.uuid4())


class MicrosoftGraphHandler(AllowAnyLOGIN):
    """
    An SMTP handler class that processes emails and sends them through the Microsoft Graph API.

    This class is responsible for parsing incoming SMTP email data, extracting content and attachments,
    and sending the email using the Microsoft Graph API with the configured application credentials.

    Attributes
    ----------
    app : ConfidentialClientApplication
        An MSAL Confidential Client Application instance used to acquire tokens for Graph API requests.

    Methods
    -------
    handle_DATA(server: SMTP, session: Session, envelope: Envelope) -> str:
        Processes the incoming SMTP data and sends the email via Microsoft Graph API.
    """

    def __init__(self):
        """
        Initializes the handler with a Confidential Client Application for Microsoft authentication.
        """
        self.app = ConfidentialClientApplication(
            client_id=os.environ["CLIENT_ID"],
            client_credential=os.environ["CLIENT_SECRET"],
            authority=os.environ["AUTHORITY"],
            token_cache=TokenCache(),
        )

    @staticmethod
    def parse_email_address(address: str) -> dict:
        """
        Parse an email address string according to RFC specifications.

        Parameters
        ----------
        address : str
            A string containing an email address, possibly including a display name.

        Returns
        -------
        dict
            A dictionary with the structure:
            {
                "emailAddress": {
                    "name": <display name>,  # Included only if available
                    "address": <email address>
                }
            }
        """
        # getaddresses returns a list of (name, address) tuples; here we only expect one address.
        parsed = getaddresses([address])
        if parsed:
            name, email = parsed[0]
            result = {"emailAddress": {"address": email}}
            if name:
                result["emailAddress"]["name"] = name
            return result
        # Fallback: return the address as provided if parsing fails.
        return {"emailAddress": {"address": address}}

    async def handle_DATA(
        self, server: SMTP, session: Session, envelope: Envelope
    ) -> str:
        """
        Handles the SMTP DATA command, parses email content and attachments,
        and sends the email through Microsoft Graph API.

        Parameters
        ----------
        server : SMTP
            The SMTP server instance.
        session : Session
            The SMTP session.
        envelope : Envelope
            The SMTP envelope, containing sender and recipient information and the email content.

        Returns
        -------
        str
            A response string indicating the result of the operation, typically "250 Message accepted for delivery" upon success.
        """
        email = Parser().parsestr(envelope.content.decode("utf-8"))
        attachments = []
        body_content = ""  # Default body content initialization
        content_type = "text"  # Default content type initialization

        # Debugging: Save the email content to a file if LOG_LEVEL is set to DEBUG
        if os.environ.get("LOG_LEVEL", "") == "DEBUG":
            os.makedirs("./debug", exist_ok=True)
            with open(f"./debug/{uuid.uuid4().hex}.html", "wb") as f:
                f.write(envelope.content)

        # Process email content and attachments
        if email.is_multipart():
            html_body = ""
            text_body = ""
            for part in email.walk():
                if part.get_content_maintype() == "multipart":
                    continue  # Skip multipart container
                content_disposition = part.get("Content-Disposition", None)
                if part.get_content_type() in ["text/plain", "text/html"]:
                    # Extract email body content
                    if (
                        not content_disposition
                        or content_disposition.lower() == "inline"
                    ):
                        payload = part.get_payload(decode=True).decode("utf-8")
                        if part.get_content_type() == "text/html":
                            html_body += payload
                        else:
                            text_body += payload
                else:
                    # Process and encode attachments
                    file_data = part.get_payload(decode=True)
                    base64_encoded = base64.b64encode(file_data).decode("utf-8")
                    attachment = {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": get_attachment_filename(part),
                        "contentType": part.get_content_type(),
                        "contentBytes": base64_encoded,
                    }
                    if "inline" in content_disposition:
                        attachment["isInline"] = True
                        # Optionally, set a content ID or use the filename as a reference in the HTML
                        # Note: Graph API does not directly use Content-ID like traditional email systems
                        attachment["contentId"] = (
                            part.get("Content-ID", "")
                            .strip("<>")
                            .replace("@mydomain.com", "")
                        )
                    attachments.append(attachment)
            # Use HTML body if available, otherwise fallback to plain text
            if html_body:
                body_content = html_body
                content_type = "html"
            else:
                body_content = text_body
                content_type = "text"
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
                        self.parse_email_address(addr)
                        for addr in email.get_all("To", [])
                    ],
                    "ccRecipients": [
                        self.parse_email_address(addr)
                        for addr in email.get_all("Cc", [])
                    ],
                    "bccRecipients": [
                        self.parse_email_address(addr)
                        for addr in email.get_all("Bcc", [])
                    ],
                    "attachments": attachments,
                },
                "saveToSentItems": os.environ.get("SAVE_TO_SENT", "true"),
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

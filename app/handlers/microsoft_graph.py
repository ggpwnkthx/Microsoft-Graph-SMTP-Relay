import orjson
from aiosmtpd.smtp import SMTP, Session, Envelope
from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.parser import Parser
from email.utils import collapse_rfc2231_value, getaddresses
from msal import ConfidentialClientApplication, TokenCache
import aiohttp
import base64
import os
import uuid

# Ensure environment variables are loaded, for example, from a .env file
if not os.environ.get("CLIENT_ID"):
    from dotenv import load_dotenv
    load_dotenv()


def get_attachment_filename(part: Message):
    filename = part.get_filename(part.get_param("name"))
    if filename:
        filename = collapse_rfc2231_value(filename)
        filename = str(make_header(decode_header(filename)))
        return filename
    return str(uuid.uuid4())


class MicrosoftGraphHandler():
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
    def _extract_email_address(address: str) -> list:
        """
        Parse an email address string and return a list of dictionaries.
        """
        parsed = getaddresses([address])
        addresses = []
        for name, addr in parsed:
            entry = {"emailAddress": {"address": addr}}
            if name:
                entry["emailAddress"]["name"] = name
            addresses.append(entry)
        return addresses if addresses else [{"emailAddress": {"address": address}}]

    @staticmethod
    def _extract_body_and_attachments(email_message: Message, debug_hex: str):
        """
        Extracts the email body (text or HTML) and attachments.

        Returns
        -------
            body_content (str): The email body.
            content_type (str): "html" if HTML body exists, otherwise "text".
            attachments (list): A list of attachment dictionaries.
        """

        attachments = []
        body = email_message.get_body(preferencelist=('html', 'plain'))
        body_content = body.get_content()
        content_type = "html" if body.get_content_type() == 'text/html' else "text"
        
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_maintype() == "multipart":
                    continue

                content_disposition = part.get("Content-Disposition", "") or ""
                part_content_type = part.get_content_type()

                if part_content_type in ["text/plain", "text/html"] and (
                    not content_disposition or "inline" in content_disposition.lower()
                ):
                    continue
                else:
                    file_data = part.get_payload(decode=True)
                    if file_data:
                        base64_encoded = base64.b64encode(
                            file_data).decode("utf-8")
                        attachment = {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": get_attachment_filename(part),
                            "contentType": part_content_type,
                            "contentBytes": base64_encoded,
                        }
                        if "inline" in content_disposition.lower():
                            attachment["isInline"] = True
                            content_id = part.get("Content-ID", "").strip("<>")
                            if content_id:
                                attachment["contentId"] = content_id.replace(
                                    "@mydomain.com", "")
                        attachments.append(attachment)

        return body_content, content_type, attachments

    async def handle_DATA(self, server: SMTP, session: Session, envelope: Envelope) -> str:
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

        # Decode the email safely
        try:
            email_content = envelope.content.decode("utf-8", errors="replace")
            email_message = Parser(policy=policy.EmailPolicy()).parsestr(email_content)
        except Exception as e:
            return f"550 Error parsing email content: {e}"

        debug_hex = uuid.uuid4().hex
        if os.environ.get("LOG_LEVEL", "").upper() == "DEBUG":
            os.makedirs("./debug", exist_ok=True)
            with open(f"./debug/{debug_hex}.email", "wb") as f:
                f.write(envelope.content)

        # Extract body and attachments using helper method
        body_content, content_type, attachments = MicrosoftGraphHandler._extract_body_and_attachments(
            email_message, debug_hex)

        # Build recipients from headers
        to_recipients = []
        cc_recipients = []
        for header, recipient_list in (("To", to_recipients), ("Cc", cc_recipients)):
            for addr in email_message.get_all(header, []):
                for part in addr.split(","):
                    part = part.strip()
                    if part:
                        recipient_list.extend(
                            MicrosoftGraphHandler._extract_email_address(part))

        # Determine bcc recipients from envelope.rcpt_tos that are not in To/Cc
        parsed_to_cc = {r["emailAddress"]["address"]
                        for r in to_recipients + cc_recipients}
        bcc_recipients = []
        for addr in envelope.rcpt_tos:
            for part in addr.split(","):
                part = part.strip()
                if part and part not in parsed_to_cc:
                    bcc_recipients.extend(
                        MicrosoftGraphHandler._extract_email_address(part))

        # Acquire an access token
        token_response = self.app.acquire_token_for_client(scopes=[".default"])
        access_token = token_response.get("access_token")
        if not access_token:
            return "550 Failed to acquire access token"

        # Build the send request payload for Microsoft Graph API
        send_payload = {
            "url": f"https://graph.microsoft.com/v1.0/users/{envelope.mail_from}/sendMail",
            "headers": {"Authorization": f"Bearer {access_token}"},
            "json": {
                "message": {
                    "subject": email_message["Subject"],
                    "body": {"contentType": content_type, "content": body_content},
                    "toRecipients": to_recipients,
                    "ccRecipients": cc_recipients,
                    "bccRecipients": bcc_recipients,
                    "attachments": attachments,
                },
                "saveToSentItems": os.environ.get("SAVE_TO_SENT", "true"),
            },
        }

        # Optionally log the payload if in DEBUG mode
        if os.environ.get("LOG_LEVEL", "").upper() == "DEBUG":
            with open(f"./debug/{debug_hex}.json", "wb") as f:
                f.write(orjson.dumps(send_payload))

        # Send the email via Microsoft Graph API
        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(**send_payload) as response:
                    if response.status == 429:
                        return "421 Temporary error: Too many requests (429) from Graph API"
                    elif response.status == 503:                        
                        return "421 Temporary error: Service Unavailable (503) from Graph API"
                    elif response.status == 504:                        
                        return "421 Temporary error: Gateway Timeout (504) from Graph API"
                    elif response.status != 202:
                        error_text = await response.text()
                        return f"550 Error from Graph API ({response.status}): {error_text}"

        # Catch network errors and return a transient error 421 code
        except aiohttp.ClientError as e:                            
            return f"421 Network error while sending email: {e}"

        except Exception as e:
            return f"550 Exception sending email: {e}"

        return "250 Message accepted for delivery"

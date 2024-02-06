from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, Session, Envelope
from email.parser import Parser
from msal import ConfidentialClientApplication, TokenCache
import aiohttp, asyncio, base64, logging, os


class RelayHandler:
    """
    RelayHandler handles SMTP email relaying through Microsoft Graph API with support for attachments.

    Methods
    -------
    get_token():
        Acquires an access token for Microsoft Graph API using client credentials.

    handle_DATA(server: SMTP, session: Session, envelope: Envelope):
        Asynchronously handles incoming SMTP data, parses the email, and sends it through Microsoft Graph API.
    """

    def get_token(self):
        """
        Acquires an access token from Microsoft Graph API for client authentication.

        Uses the MSAL (Microsoft Authentication Library) to acquire a token.

        Returns
        -------
        str
            The acquired access token if successful, None otherwise. Logs an error on failure.
        """
        result = ConfidentialClientApplication(
            client_id=os.environ["CLIENT_ID"],
            client_credential=os.environ["CLIENT_SECRET"],
            authority=os.environ["AUTHORITY"],
            token_cache=TokenCache(),
        ).acquire_token_for_client(scopes=[".default"])
        if "access_token" in result:
            return result["access_token"]
        else:
            logging.error(result)
            return None

    async def handle_DATA(self, server: SMTP, session: Session, envelope: Envelope):
        """
        Asynchronously processes the received email data, extracts contents and attachments,
        and sends the email via Microsoft Graph API.

        Parameters
        ----------
        server : SMTP
            The SMTP server instance.
        session : Session
            The SMTP session.
        envelope : Envelope
            The SMTP envelope, containing the email data.

        Returns
        -------
        str
            SMTP server response indicating the result of the email sending operation.
        """
        email = Parser().parsestr(envelope.content.decode("utf-8"))
        attachments = []
        body_content = ""  # Default body content
        content_type = "text"  # Default content type

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
                    attachments.append(
                        {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": part.get_filename(),
                            "contentType": part.get_content_type(),
                            "contentBytes": base64_encoded,
                        }
                    )

        # Construct the request payload for sending the email via Microsoft Graph API
        send = {
            "url": f"https://graph.microsoft.com/v1.0/users/{envelope.mail_from}/sendMail",
            "headers": {"Authorization": "Bearer " + self.get_token()},
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
        logging.warning(send)

        # Send the email through Microsoft Graph API
        async with aiohttp.ClientSession() as session:
            async with session.post(**send) as response:
                if response.status != 202:
                    return await response.text()
        return "250 Message accepted for delivery"


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    handler = RelayHandler()
    cont = Controller(
        handler,
        hostname=os.environ.get("HOSTNAME", "0.0.0.0"),
        port=int(os.environ.get("PORT", "25")),
    )
    cont.start()  # Start the SMTP controller
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print("User abort indicated")
    finally:
        cont.stop()  # Stop the SMTP controller on exit

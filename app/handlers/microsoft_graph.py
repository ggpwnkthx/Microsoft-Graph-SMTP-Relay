import asyncio
from hashlib import md5
import hmac
import io
import math
import secrets
import time
from typing import Optional
from aiosmtpd.smtp import SMTP, Session, Envelope, AuthResult
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
import logging

from event_bus import event_bus_instance

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

        self.access_token = ""

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
    def _extract_body_and_attachments(email_message: Message):
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
        content_type = "text"
        if body.get_content_type() == 'text/html':
            # get content from html body
            body_content = body.get_content()
            content_type = "html"
        else:
            # but get payload from plain text
            pair = dict(body.items())
            if pair.get("Content-Transfer-Encoding") == "8bit":
                # no actual encoding
                body_content = body.get_payload()
            else:
                # assume other Content-Transfer-Encoding can be handled with get_content (E.g. "quoted-printable" or "base64")
                body_content = body.get_content()
               
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
                            "isInline": False,
                            "contentId": None
                        }
                        if "inline" in content_disposition.lower():
                            attachment["isInline"] = True
                            content_id = part.get("Content-ID", "").strip("<>")
                            if content_id:
                                attachment["contentId"] = content_id

                        attachments.append(attachment)

        return body_content, content_type, attachments

    async def __create_token(self):
        token_response = self.app.acquire_token_for_client(scopes=[".default"])
        self.access_token = token_response.get("access_token")

    async def __create_draft(self, email_message, envelope):
        await event_bus_instance.publish('sender', envelope.mail_from)

         # Extract body and attachments using helper method
        body_content, content_type, attachments = MicrosoftGraphHandler._extract_body_and_attachments(email_message)

        # Build recipients from headers
        to_recipients = []
        cc_recipients = []
        reply_to = []
        for header, recipient_list in (("To", to_recipients), ("Cc", cc_recipients)):
            for addr in email_message.get_all(header, []):
                for part in addr.split(","):
                    part = part.strip()
                    if part:
                        recipient_list.extend(
                            MicrosoftGraphHandler._extract_email_address(part))

        for addr in email_message.get_all("Reply-To", []):
            for part in addr.split(","):
                part = part.strip()
                if part:
                    reply_to.extend(
                        MicrosoftGraphHandler._extract_email_address(part)
                    )

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
                    
        await event_bus_instance.publish('recipients', to_recipients, cc_recipients, bcc_recipients)
        
        # Requires Microsoft Graph permission "Mail.ReadWrite"
        send_payload = {
            "url": f"https://graph.microsoft.com/v1.0/users/{envelope.mail_from}/messages",
            "headers": {
                "Authorization": f"Bearer {self.access_token}",
                # use ImmutableId to delete the message later
                "Prefer": 'IdType="ImmutableId"'
            },
            "json": {
                "subject": email_message["Subject"],
                "body": {"contentType": content_type, "content": body_content},
                "toRecipients": to_recipients,
                "ccRecipients": cc_recipients,
                "bccRecipients": bcc_recipients,
                **({"replyTo": reply_to} if reply_to else {})
            },
        }

        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(**send_payload) as response:
                if response.status == 201:
                    data = await response.json()
                    logging.info(f"Draft message created with ID: {data['id']}")
                    return data["id"], attachments
                else:
                    error_details = await response.json()
                    logging.error(f"Failed to create draft message: {response.status} - {error_details}")
                    return None, attachments


    async def __send_draft(self, user_id: str, message_id) -> bool:
        """
        Sends the draft message.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        url = f"https://graph.microsoft.com/v1.0/users/{user_id}/messages/{message_id}/send"

        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(url, headers=headers) as response:
                if response.status == 202: # Accepted
                    logging.info("Email sent successfully with large attachment!")
                    return True
                else:
                    error_details = await response.json()
                    logging.error(f"Failed to send email: {response.status} - {error_details}")
                    return False

    async def __create_upload_session(self, user_id: str, message_id: str, file_name: str, file_size: int, is_inline: bool, content_id) -> Optional[str]:
        """
        Creates an upload session for a large attachment and returns the upload URL.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        upload_session_data = {
            "AttachmentItem": {
                "attachmentType": "file",
                "name": file_name,
                "size": file_size,
                "isInline": is_inline,
                "contentId": content_id,
            }
        }
        url = f"https://graph.microsoft.com/v1.0/users/{user_id}/messages/{message_id}/attachments/createUploadSession"

        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(url, headers=headers, json=upload_session_data) as response:
                if response.status in [200, 201, 202]: # Accepted
                    data = await response.json()
                    logging.info(f"Upload session created for '{file_name}'.")
                    logging.debug(f"Upload URL: {data['uploadUrl']}")
                    return data['uploadUrl']
                else:
                    error_details = await response.json()
                    logging.error(f"Failed to create upload session: {response.status} - {error_details}")
                    return False
    
    async def __upload_attachment_in_chunks(self, upload_url: str, file_data: bytes, chunk_size: int = 327680): # 320 KiB
        """
        Uploads a file to the given upload URL in chunks.
        Chunk size must be a multiple of 320 KiB (327,680 bytes).
        """
        file = io.BytesIO(file_data)

        file_size = len(file_data)
        num_chunks = math.ceil(file_size / chunk_size)

        logging.debug(f"Start uploading {file_size} bytes into {num_chunks} chunks")

        # Using a Semaphore to limit concurrent uploads if desired, though aiohttp handles concurrency well.
        # semaphore = asyncio.Semaphore(5) # Limit to 5 concurrent uploads if many small chunks
        async def upload_chunk(start_byte: int, end_byte: int, chunk_data: bytes, chunk_idx: int):
            # async with semaphore:
                headers = {
                    "Content-Range": f"bytes {start_byte}-{end_byte-1}/{file_size}",
                    "Content-Length": str(len(chunk_data))
                }
                # Graph API requires PUT for upload sessions
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.put(upload_url, headers=headers, data=chunk_data) as response:
                        if response.status in [200, 201, 202]: # 200 OK, 201 Created, 202 Accepted
                            # 200/201 if last chunk, 202 if intermediate chunk
                            logging.debug(f"Chunk {chunk_idx+1}/{num_chunks} uploaded (bytes {start_byte}-{end_byte-1})")
                            return True
                        else:
                            error_details = await response.json()
                            logging.error(f"Failed to upload chunk {chunk_idx+1}/{num_chunks}: {response.status} - {error_details}")
                            return False

        for i in range(num_chunks):
            start_byte = i * chunk_size
            end_byte = min((i + 1) * chunk_size, file_size)
            chunk_data = file.read(chunk_size)
            if not chunk_data: # Should not happen if calculations are correct
                break
            await upload_chunk(start_byte, end_byte, chunk_data, i)
    
    async def __delete_message(self, user_id: str, message_id) -> bool:
        """
        Sends the draft message.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        url = f"https://graph.microsoft.com/v1.0/users/{user_id}/messages/{message_id}/permanentDelete"

        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(url, headers=headers) as response:
                if response.status == 204: # Accepted
                    logging.info("Email successfully deleted!")
                    return True
                else:
                    error_details = await response.json()
                    logging.warning(f"Failed to delete email: {response.status} - {error_details}")
                    return False

    async def auth_CRAM__MD5(self, server: SMTP, args):
        smtp_user = os.environ.get("SMTP_AUTH_USER", "")
        smtp_pass = os.environ.get("SMTP_AUTH_PASS", "")

        timestamp = f"<{int(time.time())}.{secrets.token_hex(4)}@{server.hostname}>"
        challenge = timestamp.encode('utf-8')

        client = await server.challenge_auth(challenge, True)
        response = client.decode('ascii')

        parts = response.split(' ')
        username = parts[0]
        pass_hash = parts[1]

        hash_value = hmac.new(smtp_pass.encode('ascii'), challenge, md5).hexdigest()
        
        if username == smtp_user and pass_hash == hash_value:
            return AuthResult(success=True)
        return AuthResult(success=False, handled=False, message="504 Authentication failed")

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

        await event_bus_instance.publish('before_send', email_message)

        await self.__create_token()
        if not self.access_token:
            return "550 Failed to acquire access token"
        
        message_id, attachments = await self.__create_draft(email_message, envelope)

        for attachment in attachments:
            file_data = base64.b64decode(attachment['contentBytes'])
            upload_url = await self.__create_upload_session(envelope.mail_from, message_id, attachment['name'], len(file_data), is_inline=attachment['isInline'], content_id=attachment['contentId'])
            await self.__upload_attachment_in_chunks(upload_url, file_data)

        if (await event_bus_instance.publish('skip_send')):
            logging.info("Message accepted without delivery")
            return "250 Message accepted (delivery skipped)"

        await self.__send_draft(envelope.mail_from, message_id)
        if os.environ.get("SAVE_TO_SENT", "false") == 'false':
            await self.__delete_message(envelope.mail_from, message_id)

        await event_bus_instance.publish('after_send')

        return "250 Message accepted for delivery"

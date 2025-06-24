import asyncio
import logging
import os
from aiosmtpd.smtp import AuthResult, LoginPassword

from event_bus import event_bus_instance

class Authenticator():       
    """
    A simple authenticator that checks for a hardcoded username and password.
    In a real application, this would interact with a database, LDAP, etc.
    """
    def __call__(self, server, session, envelope, mechanism, auth_data):
        """
        This method is called by aiosmtpd when an AUTH command is received.

        Args:
            server: The SMTP server instance.
            session: The SMTP session object.
            envelope: The SMTP envelope object (contains email transaction details).
            mechanism: The authentication mechanism (e.g., 'PLAIN', 'LOGIN').
            auth_data: An object containing authentication data. For 'PLAIN' and 'LOGIN',
                       this will be an instance of aiosmtpd.smtp.LoginPassword.

        Returns:
            AuthResult: An AuthResult object indicating success or failure.
        """
        logging.debug(f"Authentication attempt: Mechanism={mechanism}")

        event_bus_instance.publishSync('before_auth', auth_data)

        smtp_user = os.environ.get("SMTP_AUTH_USER", "")
        smtp_pass = os.environ.get("SMTP_AUTH_PASS", "")

        if isinstance(auth_data, LoginPassword):
            username = auth_data.login.decode('utf-8')
            password = auth_data.password.decode('utf-8')

            logging.debug(f"Attempting to authenticate user: {username}")

            # Hardcoded credentials for demonstration
            if username == smtp_user and password == smtp_pass:
                logging.info(f"Authentication successful for user: {username}")
                event_bus_instance.publishSync('after_auth', auth_data)
                
                return AuthResult(success=True)
            else:
                logging.warning(f"Authentication failed for user: {username}")
                return AuthResult(success=False, handled=False, message="535 Invalid credentials")
        else:
            logging.error(f"Unsupported auth_data type for mechanism {mechanism}: {type(auth_data)}")
            return AuthResult(success=False, handled=False, message="504 Authentication mechanism not supported")

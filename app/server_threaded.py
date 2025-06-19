from aiosmtpd.controller import Controller
from handlers.authenticator import Authenticator
from handlers.microsoft_graph import MicrosoftGraphHandler

import asyncio
import logging
import os
import signal
import sys

# Load environment variables from a .env file if the CLIENT_ID is not set in the environment
if not os.environ.get("CLIENT_ID"):
    from dotenv import load_dotenv
    load_dotenv()

# Set up logging based on the environment variable LOG_LEVEL
if __name__ == "__main__":
    # Match the log level environment variable and configure logging appropriately
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        stream=sys.stdout,
        #filename=log_file if log_file_enabled else None,  # Only set file logging if enabled
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=getattr(logging, log_level, logging.INFO),  # Fallback to INFO if LOG_LEVEL is invalid
        force=True  # Ensure previous settings are overridden
    )

# Get hostname and port from environment variables with defaults
hostname = os.environ.get("SMTP_RELAY_HOSTNAME", "0.0.0.0")
port = int(os.environ.get("SMTP_RELAY_PORT", "25"))

# Ensure required environment variables are set
required_env_vars = ["CLIENT_ID", "CLIENT_SECRET", "AUTHORITY"]
for var in required_env_vars:
    if not os.environ.get(var):
        logging.error(f"Environment variable {var} is required.")
        sys.exit(1)

smtp_user = os.environ.get("SMTP_AUTH_USER", "")
smtp_pass = os.environ.get("SMTP_AUTH_PASS", "")
auth_required = bool(smtp_user and smtp_user.strip()) and bool(smtp_pass and smtp_pass.strip())

authenticator = Authenticator()

# Initialize the SMTP server controller with Microsoft Graph handler
controller = Controller(
    MicrosoftGraphHandler(),
    hostname=hostname,
    port=port,
    authenticator=authenticator,
    require_starttls=False,
    auth_require_tls=False,
    auth_required=auth_required,
)

loop = asyncio.new_event_loop()

# Register signal handlers for graceful shutdown
for sig in ("SIGINT", "SIGTERM"):
    loop.add_signal_handler(getattr(signal, sig), loop.stop)

try:
    controller.start()
    logging.info(f"Started SMTP service on {hostname}:{port}")
    # Run the event loop until a stop signal is received
    loop.run_forever()
except Exception as e:
    logging.error(f"Error occurred: {e}")
finally:
    # Stop the SMTP server and close the event loop
    controller.stop()
    loop.close()
    logging.info("SMTP server stopped.")

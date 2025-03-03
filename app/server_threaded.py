from aiosmtpd.controller import Controller
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
    match os.environ.get("LOG_LEVEL", "INFO"):
        case "DEBUG":
            logging.basicConfig(level=logging.DEBUG)
        case "INFO":
            logging.basicConfig(level=logging.INFO)
        case "WARNING":
            logging.basicConfig(level=logging.WARNING)
        case _:
            logging.basicConfig(level=logging.ERROR)

# Get hostname and port from environment variables with defaults
hostname = os.environ.get("SMTP_RELAY_HOSTNAME", "0.0.0.0")
port = int(os.environ.get("SMTP_RELAY_PORT", "25"))

# Ensure required environment variables are set
required_env_vars = ["CLIENT_ID", "CLIENT_SECRET", "AUTHORITY"]
for var in required_env_vars:
    if not os.environ.get(var):
        logging.error(f"Environment variable {var} is required.")
        sys.exit(1)

# Initialize the SMTP server controller with Microsoft Graph handler
controller = Controller(
    MicrosoftGraphHandler(),
    hostname=hostname,
    port=port,
    require_starttls=False,
    auth_require_tls=False,
    auth_required=False,
)

# Create an asyncio Event to signal server shutdown
stop_event = asyncio.Event()

def stop():
    """
    Signal the event loop to stop by setting the stop event.
    """
    stop_event.set()

loop = asyncio.new_event_loop()

# Register signal handlers for graceful shutdown
for sig in ("SIGINT", "SIGTERM"):
    loop.add_signal_handler(getattr(signal, sig), stop)

try:
    controller.start()
    logging.info(f"Started SMTP service on {hostname}:{port}")
    # Run the event loop until a stop signal is received
    loop.run_until_complete(stop_event.wait())
except Exception as e:
    logging.error(f"Error occurred: {e}")
finally:
    # Stop the SMTP server and close the event loop
    controller.stop()
    loop.close()
    logging.info("SMTP server stopped.")

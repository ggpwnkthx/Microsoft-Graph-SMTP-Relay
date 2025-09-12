from microsoft_graph_smtp import MicrosoftGraphSmtp
from event_bus import event_bus_instance

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Load environment variables from a .env file if the CLIENT_ID is not set in the environment
if not os.environ.get("CLIENT_ID"):
    from dotenv import load_dotenv
    load_dotenv()

# Set up logging based on the environment variable LOG_LEVEL
if __name__ == "__main__":

    #Enable filesystem logging if configured with LOG_FILE_ENABLED
    log_file_enabled = os.environ.get("LOG_FILE_ENABLED", "false").lower() == "true"
    log_file = os.environ.get("LOG_FILE", "/var/log/smtp/smtp_relay.log") if log_file_enabled else None
    if log_file_enabled and log_file:
        #create log file path if it does not exist
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)


    # Match the log level environment variable and configure logging appropriately
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    config = {
        "format": "%(asctime)s - %(levelname)s - %(message)s",
        "level": getattr(logging, log_level, logging.INFO), # Fallback to INFO if LOG_LEVEL is invalid
        "force": True # Ensure previous settings are overridden
    }
    if log_file_enabled:
        config["filename"] = log_file
    else:
        config["stream"] = sys.stdout
    logging.basicConfig(**config)

# Ensure required environment variables are set
required_env_vars = ["CLIENT_ID", "CLIENT_SECRET", "AUTHORITY"]
for var in required_env_vars:
    if not os.environ.get(var):
        logging.error(f"Environment variable {var} is required.")
        sys.exit(1)

controller = MicrosoftGraphSmtp()

class GracefulExit(SystemExit):
    code = 1

def raise_graceful_exit(*args):
    loop.stop()
    event_bus_instance.shutdown()
    raise GracefulExit()

loop = asyncio.get_event_loop()
signal.signal(signal.SIGINT, raise_graceful_exit)
signal.signal(signal.SIGTERM, raise_graceful_exit)

try:
    controller.start()
    logging.info(f"Started SMTP service on {controller.hostname}:{controller.port}")
    # Run the event loop until a stop signal is received
    loop.run_forever()
except Exception as e:
    logging.error(f"Error occurred: {e}")
finally:
    # Stop the SMTP server and close the event loop
    controller.stop()
    loop.close()
    logging.info("SMTP server stopped.")

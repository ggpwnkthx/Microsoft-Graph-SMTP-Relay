from aiosmtpd.controller import Controller
from handlers.microsoft_graph import MicrosoftGraphHandler
import asyncio, logging, os, signal

if not os.environ.get("CLIENT_ID"):
    from dotenv import load_dotenv
    load_dotenv()

if __name__ == "__main__":
    match os.environ.get("LOG_LEVEL", "INFO"):
        case "DEBUG":
            logging.basicConfig(level=logging.DEBUG)
        case "INFO":
            logging.basicConfig(level=logging.INFO)
        case "WARNING":
            logging.basicConfig(level=logging.WARNING)
        case _:
            logging.basicConfig(level=logging.ERROR)

    hostname = os.environ.get("SMTP_RELAY_HOSTNAME", "0.0.0.0")
    port = int(os.environ.get("SMTP_RELAY_PORT", "25"))
    controller = Controller(
        MicrosoftGraphHandler(),
        hostname=hostname,
        port=port,
        require_starttls=False,
        auth_require_tls=False,
        auth_required=False,
    )
    
    stop_event = asyncio.Event()

    def stop():
        stop_event.set()

    loop = asyncio.get_event_loop()

    # Registering the signal handlers to stop the loop
    for sig in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, sig), stop)

    controller.start()
    logging.info(f"Started SMTP service on {hostname}:{port}")

    try:
        loop.run_until_complete(stop_event.wait())
    finally:
        controller.stop()
        loop.close()
        logging.info("SMTP server stopped.")

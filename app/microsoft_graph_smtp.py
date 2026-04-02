from glob import glob
import importlib
import logging
import os
from pathlib import Path
import pkgutil
import sys
import ipaddress
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP

from handlers.authenticator import Authenticator
from handlers.microsoft_graph import MicrosoftGraphHandler

class MicrosoftGraphSmtpSMTP(SMTP):
    value = os.environ.get("AIOSMTPD_LINE_LENGTH_LIMIT", 1000)
    try:
        line_length_limit = int(value)
    except ValueError:
        line_length_limit = 1000
    line_length_limit = max(1000, min(line_length_limit, 65535))

class MicrosoftGraphSmtp(Controller):
    def __init__(self):

        # Parse and validate allowed ips
        allowed_ips = os.getenv("ALLOWED_IPS", "")
        allowed_networks = set()
        for item in allowed_ips.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                network = ipaddress.ip_network(item, strict=False)
                allowed_networks.add(network)
            except ValueError:
                pass
        logging.debug("Allowed networks initialized: %s", allowed_networks)

        self.middleware_dir = os.environ.get("MIDDLEWARE_DIR", "app/middleware")
        self.msGraphHandler = MicrosoftGraphHandler(allowed_networks=allowed_networks)

        hostname = os.environ.get("SMTP_RELAY_HOSTNAME", "0.0.0.0")
        port = int(os.environ.get("SMTP_RELAY_PORT", "25"))

        smtp_user = os.environ.get("SMTP_AUTH_USER", "")
        smtp_pass = os.environ.get("SMTP_AUTH_PASS", "")
        auth_required = bool(smtp_user and smtp_user.strip()) and bool(smtp_pass and smtp_pass.strip())

        authenticator = Authenticator()

        super().__init__(self.msGraphHandler,
                         hostname,
                         port,
                         authenticator=authenticator,
                         require_starttls=False,
                         auth_require_tls=False,
                         auth_required=auth_required)
        
        self.load_middleware()

    def factory(self):
        return MicrosoftGraphSmtpSMTP(self.handler, **self.SMTP_kwargs)

    def load_middleware(self):
        pkg_dir = Path(self.middleware_dir) # instead of glob
        pkg_name = ".".join(pkg_dir.parts)
        # Ensure our package directory is on sys.path (if not already)
        if str(Path.cwd()) not in sys.path:
            sys.path.insert(0, str(Path.cwd()))
        # Iterate all top-level modules under app/middleware
        for _, module_name, _ in pkgutil.iter_modules([str(pkg_dir)]):
            full_name = f"{pkg_name}.{module_name}"
            try:
                module = importlib.import_module(full_name)
            except Exception as e:
                logging.error(f"[Middleware Loader] FAILED to import {full_name!r}: {e}")
                continue
            MiddlewareClass = getattr(module, "Middleware", None)
            if MiddlewareClass is None:
                # No Middleware class in that module; skip
                continue
            try:
                MiddlewareClass(self.msGraphHandler)
            except Exception as e:
                logging.error(f"[Middleware Loader] ERROR instantiating {full_name!r}: {e}")
                continue
            logging.debug(f"[Middleware Loader] LOADED {full_name!r} successfully.")

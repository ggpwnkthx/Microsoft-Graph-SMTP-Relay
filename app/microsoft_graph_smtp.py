from glob import glob
import importlib
import logging
import os
from pathlib import Path
import pkgutil
import sys
from aiosmtpd.controller import Controller

from handlers.authenticator import Authenticator
from handlers.microsoft_graph import MicrosoftGraphHandler

class MicrosoftGraphSmtp(Controller):
    def __init__(self):
        self.middleware_dir = os.environ.get("MIDDLEWARE_DIR", "app/middleware")
        self.msGraphHandler = MicrosoftGraphHandler()

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

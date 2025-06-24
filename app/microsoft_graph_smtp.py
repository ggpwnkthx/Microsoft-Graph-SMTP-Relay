from glob import glob
import importlib
import os
import sys
from aiosmtpd.controller import Controller

from handlers.authenticator import Authenticator
from handlers.microsoft_graph import MicrosoftGraphHandler

class MicrosoftGraphSmtp(Controller):
    def __init__(self):
        self.middleware_glob = os.environ.get("MIDDLEWARE_GLOB", "app/middleware/*.py")
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
        middleware_files = glob(self.middleware_glob)

        for file in middleware_files:
            spec = importlib.util.spec_from_file_location("module.name", file)
            module = importlib.util.module_from_spec(spec)
            sys.modules["module.name"] = module
            spec.loader.exec_module(module)
            class_ = getattr(module, 'Middleware')
            class_(self.msGraphHandler)
from aiosmtpd.smtp import SMTP, AuthResult
from typing import List


class AllowAnyLOGIN:
    async def auth_LOGIN(self, server: SMTP, args: List[str]):
        return AuthResult(success=True)

    async def auth_PLAIN(self, server: SMTP, args: List[str]):
        return AuthResult(success=True)

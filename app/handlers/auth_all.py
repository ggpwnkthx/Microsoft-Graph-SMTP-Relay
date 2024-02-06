from aiosmtpd.smtp import SMTP, AuthResult
from typing import List


class AllowAnyLOGIN:
    """
    A custom authentication handler class for an SMTP server that allows
    any LOGIN and PLAIN authentication attempts to succeed.

    This class is intended for development or testing environments where
    authentication is required but the validation of credentials is not necessary.

    Methods
    -------
    auth_LOGIN(server: SMTP, args: List[str]) -> AuthResult:
        Always authorizes LOGIN authentication attempts.

    auth_PLAIN(server: SMTP, args: List[str]) -> AuthResult:
        Always authorizes PLAIN authentication attempts.
    """

    async def auth_LOGIN(self, server: SMTP, args: List[str]) -> AuthResult:
        """
        Handle LOGIN authentication attempts by always authorizing them.

        Parameters
        ----------
        server : SMTP
            The instance of the SMTP server calling this authentication method.
        args : List[str]
            A list of arguments provided with the LOGIN command. Typically includes
            the username and password, but in this case, they are not validated.

        Returns
        -------
        AuthResult
            An authentication result indicating successful authentication.
        """
        return AuthResult(success=True)

    async def auth_PLAIN(self, server: SMTP, args: List[str]) -> AuthResult:
        """
        Handle PLAIN authentication attempts by always authorizing them.

        Parameters
        ----------
        server : SMTP
            The instance of the SMTP server calling this authentication method.
        args : List[str]
            A list of arguments provided with the PLAIN command. This usually includes
            authorization identity, authentication identity, and password, but here,
            they are not validated.

        Returns
        -------
        AuthResult
            An authentication result indicating successful authentication.
        """
        return AuthResult(success=True)

class RedditManagerError(Exception):
    """Base error with a user-safe message."""


class ConfigurationError(RedditManagerError):
    """The declarative community configuration is invalid."""


class CredentialError(RedditManagerError):
    """OAuth credentials are absent or malformed."""


class AuthorizationError(RedditManagerError):
    """The OAuth authorization flow could not be completed securely."""


class DependencyError(RedditManagerError):
    """A runtime dependency needed for online commands is unavailable."""


class ConfirmationError(RedditManagerError):
    """A destructive-capable command was not explicitly confirmed."""

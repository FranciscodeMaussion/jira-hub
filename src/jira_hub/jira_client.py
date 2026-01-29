"""Jira API client with keyring-based authentication."""

import contextlib

import keyring
from jira import JIRA
from jira.exceptions import JIRAError

SERVICE_NAME = "jh"
KEYRING_SERVER_KEY = "jira_server"
KEYRING_EMAIL_KEY = "jira_email"
KEYRING_TOKEN_KEY = "jira_token"


class JiraAuthError(Exception):
    """Raised when Jira authentication fails."""


class JiraClient:
    """Jira API wrapper with secure credential storage."""

    def __init__(self) -> None:
        """Initialize client by loading credentials from keyring."""
        self._server: str | None = None
        self._email: str | None = None
        self._token: str | None = None
        self._client: JIRA | None = None
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load credentials from system keyring."""
        self._server = keyring.get_password(SERVICE_NAME, KEYRING_SERVER_KEY)
        self._email = keyring.get_password(SERVICE_NAME, KEYRING_EMAIL_KEY)
        self._token = keyring.get_password(SERVICE_NAME, KEYRING_TOKEN_KEY)

    @property
    def is_authenticated(self) -> bool:
        """Check if credentials are stored."""
        return all([self._server, self._email, self._token])

    def verify_credentials(self) -> bool:
        """Verify stored credentials are still valid by calling the Jira API.

        Returns:
            True if the API call succeeds, False otherwise.
        """
        if not self.is_authenticated:
            return False
        try:
            self._get_client().myself()
            return True
        except Exception:
            return False

    @property
    def server_url(self) -> str | None:
        """Return the configured Jira server URL."""
        return self._server

    def _get_client(self) -> JIRA:
        """Get or create authenticated Jira client."""
        if self._client is None:
            if not self.is_authenticated:
                raise JiraAuthError("Not authenticated. Run 'jh login' first.")
            self._client = JIRA(
                server=self._server,
                basic_auth=(self._email, self._token),
            )
        return self._client

    @staticmethod
    def login(server: str, email: str, token: str) -> None:
        """Validate credentials and store in keyring.

        Args:
            server: Jira server URL (e.g., https://company.atlassian.net)
            email: Jira account email
            token: Jira API token

        Raises:
            JiraAuthError: If credentials are invalid
        """
        # Normalize server URL
        server = server.rstrip("/")

        # Validate credentials by attempting to connect
        try:
            client = JIRA(server=server, basic_auth=(email, token))
            # Test the connection by fetching current user
            client.myself()
        except JIRAError as e:
            raise JiraAuthError(f"Authentication failed: {e.text}") from e
        except Exception as e:
            raise JiraAuthError(f"Connection failed: {e}") from e

        # Store credentials in keyring
        keyring.set_password(SERVICE_NAME, KEYRING_SERVER_KEY, server)
        keyring.set_password(SERVICE_NAME, KEYRING_EMAIL_KEY, email)
        keyring.set_password(SERVICE_NAME, KEYRING_TOKEN_KEY, token)

    @staticmethod
    def update_token(token: str) -> None:
        """Update only the API token, keeping server and email.

        Args:
            token: New Jira API token

        Raises:
            JiraAuthError: If not logged in or token is invalid
        """
        server = keyring.get_password(SERVICE_NAME, KEYRING_SERVER_KEY)
        email = keyring.get_password(SERVICE_NAME, KEYRING_EMAIL_KEY)

        if not server or not email:
            raise JiraAuthError("No existing credentials found. Run 'jh login' first.")

        # Validate the new token
        try:
            client = JIRA(server=server, basic_auth=(email, token))
            client.myself()
        except JIRAError as e:
            raise JiraAuthError(f"Authentication failed: {e.text}") from e
        except Exception as e:
            raise JiraAuthError(f"Connection failed: {e}") from e

        # Update only the token
        keyring.set_password(SERVICE_NAME, KEYRING_TOKEN_KEY, token)

    @staticmethod
    def logout() -> None:
        """Remove stored credentials from keyring."""
        for key in [KEYRING_SERVER_KEY, KEYRING_EMAIL_KEY, KEYRING_TOKEN_KEY]:
            with contextlib.suppress(keyring.errors.PasswordDeleteError):
                keyring.delete_password(SERVICE_NAME, key)

    def get_issue(self, key: str) -> dict:
        """Fetch issue details from Jira.

        Args:
            key: Issue key (e.g., PROJ-123)

        Returns:
            Dict with issue details: key, summary, description, issue_type
        """
        client = self._get_client()
        try:
            issue = client.issue(key)
            return {
                "key": issue.key,
                "summary": issue.fields.summary,
                "description": issue.fields.description or "",
                "issue_type": issue.fields.issuetype.name,
            }
        except JIRAError as e:
            raise JiraAuthError(f"Failed to fetch issue {key}: {e.text}") from e

    def get_epic(self, key: str) -> dict | None:
        """Get the parent epic of an issue.

        Args:
            key: Issue key (e.g., PROJ-123)

        Returns:
            Dict with epic details or None if no epic
        """
        client = self._get_client()
        try:
            issue = client.issue(key)

            # Check for parent field (used in next-gen projects)
            if hasattr(issue.fields, "parent") and issue.fields.parent:
                parent = issue.fields.parent
                if (
                    hasattr(parent.fields, "issuetype")
                    and parent.fields.issuetype.name == "Epic"
                ):
                    return {
                        "key": parent.key,
                        "summary": parent.fields.summary,
                    }

            # Check for epic link field (used in classic projects)
            # The field name varies by instance, commonly customfield_10014
            for field_name in dir(issue.fields):
                if "epic" in field_name.lower():
                    epic_key = getattr(issue.fields, field_name, None)
                    if epic_key and isinstance(epic_key, str):
                        try:
                            epic = client.issue(epic_key)
                            return {
                                "key": epic.key,
                                "summary": epic.fields.summary,
                            }
                        except JIRAError:
                            continue

            return None
        except JIRAError:
            return None

    def get_linked_issues(self, key: str) -> list[dict]:
        """Get all linked issues for an issue.

        Args:
            key: Issue key (e.g., PROJ-123)

        Returns:
            List of dicts with linked issue details
        """
        client = self._get_client()
        linked = []

        try:
            issue = client.issue(key)
            for link in issue.fields.issuelinks:
                linked_issue = None
                link_type = link.type.name

                if hasattr(link, "outwardIssue"):
                    linked_issue = link.outwardIssue
                    direction = link.type.outward
                elif hasattr(link, "inwardIssue"):
                    linked_issue = link.inwardIssue
                    direction = link.type.inward

                if linked_issue:
                    linked.append(
                        {
                            "key": linked_issue.key,
                            "summary": linked_issue.fields.summary,
                            "link_type": link_type,
                            "direction": direction,
                        }
                    )
        except JIRAError:
            pass

        return linked

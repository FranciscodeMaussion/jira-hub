"""Git and GitHub CLI utilities."""

import re
import shutil
import subprocess


class GitError(Exception):
    """Raised when a git operation fails."""


def _run_command(args: list[str], check: bool = True) -> str:
    """Run a command and return its output.

    Args:
        args: Command and arguments
        check: Raise exception on non-zero exit

    Returns:
        Command stdout

    Raises:
        GitError: If command fails and check is True
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=check,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Command failed: {' '.join(args)}\n{e.stderr}") from e


def is_git_repo() -> bool:
    """Check if current directory is inside a git repository."""
    try:
        _run_command(["git", "rev-parse", "--git-dir"])
        return True
    except GitError:
        return False


def get_current_branch() -> str:
    """Get the current git branch name.

    Returns:
        Current branch name

    Raises:
        GitError: If not in a git repo or not on a branch
    """
    if not is_git_repo():
        raise GitError("Not in a git repository")

    branch = _run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    if branch == "HEAD":
        raise GitError("Not on a branch (detached HEAD state)")

    return branch


def extract_ticket_id(branch_name: str) -> str | None:
    """Extract Jira ticket ID from branch name.

    Expects branch names like:
    - PROJ-123-description
    - PROJ-123/description
    - feature/PROJ-123-description

    Args:
        branch_name: Git branch name

    Returns:
        Ticket ID (e.g., PROJ-123) or None if not found
    """
    # Match Jira ticket pattern: PROJECT-NUMBER
    match = re.search(r"([A-Z][A-Z0-9]+-\d+)", branch_name)
    return match.group(1) if match else None


def get_last_commit_message() -> str:
    """Get the most recent commit message.

    Returns:
        Last commit message (subject + body)

    Raises:
        GitError: If not in a git repo or no commits
    """
    if not is_git_repo():
        raise GitError("Not in a git repository")

    return _run_command(["git", "log", "-1", "--pretty=%B"])


def get_last_commit_subject() -> str:
    """Get just the subject line of the last commit.

    Returns:
        Last commit subject line

    Raises:
        GitError: If not in a git repo or no commits
    """
    if not is_git_repo():
        raise GitError("Not in a git repository")

    return _run_command(["git", "log", "-1", "--pretty=%s"])


def is_gh_installed() -> bool:
    """Check if GitHub CLI (gh) is installed."""
    return shutil.which("gh") is not None


def is_gh_authenticated() -> bool:
    """Check if GitHub CLI is authenticated."""
    if not is_gh_installed():
        return False
    try:
        _run_command(["gh", "auth", "status"])
        return True
    except GitError:
        return False


def get_pr_for_branch(branch: str) -> dict | None:
    """Check if a PR exists for the given branch.

    Args:
        branch: Branch name to check

    Returns:
        Dict with PR info (number, url, title) or None if no PR exists
    """
    if not is_gh_installed():
        raise GitError("GitHub CLI (gh) is not installed")

    try:
        output = _run_command(
            [
                "gh",
                "pr",
                "list",
                "--head",
                branch,
                "--json",
                "number,url,title",
                "--limit",
                "1",
            ]
        )

        if not output or output == "[]":
            return None

        import json

        prs = json.loads(output)
        return prs[0] if prs else None
    except GitError:
        return None


def create_pr(title: str, body: str, base: str | None = None) -> dict:
    """Create a pull request using GitHub CLI.

    Args:
        title: PR title
        body: PR body/description
        base: Base branch (defaults to repo default)

    Returns:
        Dict with PR info (number, url)

    Raises:
        GitError: If PR creation fails
    """
    if not is_gh_installed():
        raise GitError(
            "GitHub CLI (gh) is not installed.\n"
            "Install it from: https://cli.github.com/"
        )

    if not is_gh_authenticated():
        raise GitError(
            "GitHub CLI is not authenticated.\nRun 'gh auth login' to authenticate."
        )

    args = ["gh", "pr", "create", "--title", title, "--body", body]

    if base:
        args.extend(["--base", base])

    _run_command(args)

    import json

    # Get the PR details
    pr_info = _run_command(["gh", "pr", "view", "--json", "number,url,title"])
    return json.loads(pr_info)


def get_remote_url() -> str | None:
    """Get the remote origin URL.

    Returns:
        Remote URL or None if not configured
    """
    try:
        return _run_command(["git", "remote", "get-url", "origin"])
    except GitError:
        return None


def push_branch(branch: str, set_upstream: bool = True) -> None:
    """Push the current branch to remote.

    Args:
        branch: Branch name to push
        set_upstream: Set upstream tracking

    Raises:
        GitError: If push fails
    """
    args = ["git", "push"]
    if set_upstream:
        args.extend(["--set-upstream", "origin", branch])
    else:
        args.append("origin")
        args.append(branch)

    _run_command(args)

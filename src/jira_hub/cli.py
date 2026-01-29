"""Command-line interface for jita."""

import re

import click

from jira_hub.git_utils import (
    GitError,
    create_pr,
    extract_ticket_id,
    get_current_branch,
    get_last_commit_message,
    get_pr_for_branch,
    is_gh_authenticated,
    is_gh_installed,
    is_git_repo,
    push_branch,
)
from jira_hub.jira_client import JiraAuthError, JiraClient
from jira_hub.pr_formatter import format_pr_body, format_pr_title


@click.group()
@click.version_option()
def main() -> None:
    """jh - Jira + gh integration CLI."""


@main.command()
def login() -> None:
    """Authenticate with Jira and store credentials securely."""
    click.echo("Jira Authentication Setup")
    click.echo("=" * 40)
    click.echo()

    # Prompt for credentials
    server = click.prompt(
        "Jira server URL",
        default="https://yourcompany.atlassian.net",
    )
    email = click.prompt("Email address")
    token = click.prompt("API token", hide_input=True)

    click.echo()
    click.echo("Validating credentials...")

    try:
        JiraClient.login(server, email, token)
        click.secho("Successfully authenticated!", fg="green")
        click.echo(f"Credentials stored in system keyring for {server}")
    except JiraAuthError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1) from None


@main.command()
def logout() -> None:
    """Remove stored Jira credentials."""
    JiraClient.logout()
    click.secho("Credentials removed from keyring.", fg="yellow")


@main.command("update-token")
def update_token() -> None:
    """Update the Jira API token (keeps server and email)."""
    client = JiraClient()

    if not client.server_url:
        click.secho(
            "Error: No existing credentials found.\nRun 'jh login' first.",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    click.echo(f"Updating token for {client.server_url}")
    token = click.prompt("New API token", hide_input=True)

    click.echo("Validating token...")

    try:
        JiraClient.update_token(token)
        click.secho("Token updated successfully!", fg="green")
    except JiraAuthError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1) from None


@main.command()
def status() -> None:
    """Show current authentication and git status."""
    client = JiraClient()

    click.echo("Authentication Status")
    click.echo("-" * 30)
    if client.is_authenticated:
        click.echo(f"  Server: {client.server_url}")
        click.echo("  Verifying credentials...")
        if client.verify_credentials():
            click.secho("Jira: Authenticated (verified)", fg="green")
        else:
            click.secho(
                "Jira: Credentials stored but invalid or expired",
                fg="red",
            )
            click.echo("  Run 'jh login' or 'jh update-token' to fix")
    else:
        click.secho("Jira: Not authenticated", fg="yellow")
        click.echo("  Run 'jh login' to authenticate")

    click.echo()

    click.echo("GitHub CLI Status")
    click.echo("-" * 30)
    if is_gh_installed():
        click.secho("gh: Installed", fg="green")
        if is_gh_authenticated():
            click.secho("gh: Authenticated", fg="green")
        else:
            click.secho("gh: Not authenticated", fg="yellow")
            click.echo("  Run 'gh auth login' to authenticate")
    else:
        click.secho("gh: Not installed", fg="red")
        click.echo("  Install from: https://cli.github.com/")

    click.echo()

    click.echo("Git Status")
    click.echo("-" * 30)
    if is_git_repo():
        click.secho("Repository: Yes", fg="green")
        try:
            branch = get_current_branch()
            click.echo(f"  Branch: {branch}")
            ticket = extract_ticket_id(branch)
            if ticket:
                click.echo(f"  Detected ticket: {ticket}")
            else:
                click.secho("  No ticket ID detected in branch name", fg="yellow")
        except GitError as e:
            click.echo(f"  {e}")
    else:
        click.secho("Repository: No (not in a git repo)", fg="yellow")


@main.command()
@click.option(
    "--title",
    "-t",
    help="Override PR title (default: ticket summary)",
)
@click.option(
    "--body",
    "-b",
    help="Override PR description (default: last commit message)",
)
@click.option(
    "--base",
    help="Base branch for the PR (default: repo default branch)",
)
@click.option(
    "--push/--no-push",
    default=True,
    help="Push branch before creating PR (default: true)",
)
@click.option(
    "--additional",
    "-a",
    multiple=True,
    help="Additional Jira ticket IDs to reference (repeatable, e.g. -a PROJ-153 -a PROJ-200)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be created without actually creating the PR",
)
def pr(
    title: str | None,
    body: str | None,
    base: str | None,
    push: bool,
    additional: tuple[str, ...],
    dry_run: bool,
) -> None:
    """Create a PR with Jira ticket references.

    Extracts the Jira ticket ID from the current branch name,
    fetches ticket details, and creates a PR with formatted
    references to the Jira ticket, epic, and linked issues.
    """
    # Check prerequisites
    if not is_git_repo():
        click.secho("Error: Not in a git repository", fg="red", err=True)
        raise SystemExit(1)

    if not is_gh_installed():
        click.secho(
            "Error: GitHub CLI (gh) is not installed.\n"
            "Install it from: https://cli.github.com/",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    if not is_gh_authenticated():
        click.secho(
            "Error: GitHub CLI is not authenticated.\n"
            "Run 'gh auth login' to authenticate.",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    # Get current branch and extract ticket ID
    try:
        branch = get_current_branch()
    except GitError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1) from None

    ticket_id = extract_ticket_id(branch)
    if not ticket_id:
        click.secho(
            f"Error: Could not extract Jira ticket ID from branch '{branch}'.\n"
            "Branch name should contain a ticket ID like 'PROJ-123'.",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    # Validate additional ticket IDs
    ticket_pattern = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
    for aid in additional:
        if not ticket_pattern.match(aid):
            click.secho(
                f"Error: Invalid ticket ID '{aid}'.\n"
                "Ticket IDs must match the pattern PROJ-123 (e.g. CORE-42, AB1-999).",
                fg="red",
                err=True,
            )
            raise SystemExit(1)

    click.echo(f"Branch: {branch}")
    click.echo(f"Ticket: {ticket_id}")
    if additional:
        click.echo(f"Additional: {', '.join(additional)}")
    click.echo()

    # Check for existing PR
    existing_pr = get_pr_for_branch(branch)
    if existing_pr:
        click.secho(
            f"A PR already exists for this branch:\n"
            f"  {existing_pr['url']}\n"
            f"  Title: {existing_pr['title']}",
            fg="yellow",
        )
        raise SystemExit(0)

    # Initialize Jira client
    client = JiraClient()
    if not client.is_authenticated:
        click.secho(
            "Error: Not authenticated with Jira.\nRun 'jh login' first.",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    # Fetch Jira ticket details
    click.echo("Fetching Jira ticket details...")
    try:
        ticket = client.get_issue(ticket_id)
        epic = client.get_epic(ticket_id)
        linked_issues = client.get_linked_issues(ticket_id)
    except JiraAuthError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise SystemExit(1) from None

    click.echo(f"  Title: {ticket['summary']}")
    if epic:
        click.echo(f"  Epic: {epic['key']} - {epic['summary']}")
    if linked_issues:
        click.echo(f"  Linked issues: {len(linked_issues)}")

    # Fetch additional ticket details
    additional_tickets: list[dict] = []
    for aid in additional:
        try:
            add_ticket = client.get_issue(aid)
            additional_tickets.append(add_ticket)
            click.echo(f"  Additional: {add_ticket['key']} - {add_ticket['summary']}")
        except JiraAuthError as e:
            click.secho(f"Error fetching {aid}: {e}", fg="red", err=True)
            raise SystemExit(1) from None

    click.echo()

    # Get description from last commit if not provided
    if not body:
        try:
            body = get_last_commit_message()
        except GitError:
            body = ""

    # Format PR title and body
    additional_keys = [t["key"] for t in additional_tickets] or None
    pr_title = title or format_pr_title(
        ticket_id, ticket["summary"], additional_keys=additional_keys
    )
    pr_body = format_pr_body(
        description=body,
        ticket=ticket,
        jira_url=client.server_url,
        epic=epic,
        linked_issues=linked_issues if linked_issues else None,
        additional_tickets=additional_tickets or None,
    )

    # Show preview in dry-run mode
    if dry_run:
        click.echo("=" * 60)
        click.echo("PR Preview (dry-run)")
        click.echo("=" * 60)
        click.echo()
        click.secho(f"Title: {pr_title}", fg="cyan")
        click.echo()
        click.echo("Body:")
        click.echo("-" * 40)
        click.echo(pr_body)
        click.echo("-" * 40)
        click.echo()
        click.secho("Dry-run complete. No PR was created.", fg="yellow")
        return

    # Push branch if requested
    if push:
        click.echo("Pushing branch to remote...")
        try:
            push_branch(branch)
            click.echo("Branch pushed.")
        except GitError as e:
            # Branch might already be pushed
            if "Everything up-to-date" not in str(e):
                click.secho(f"Warning: {e}", fg="yellow")

    # Create the PR
    click.echo("Creating pull request...")
    try:
        pr_info = create_pr(title=pr_title, body=pr_body, base=base)
        click.echo()
        click.secho("Pull request created!", fg="green")
        click.echo(f"  URL: {pr_info['url']}")
    except GitError as e:
        click.secho(f"Error creating PR: {e}", fg="red", err=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

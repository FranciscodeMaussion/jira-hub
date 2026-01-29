"""PR description formatter with Jira references."""


def format_pr_body(
    description: str,
    ticket: dict,
    jira_url: str,
    epic: dict | None = None,
    linked_issues: list[dict] | None = None,
    additional_tickets: list[dict] | None = None,
) -> str:
    """Format PR body with Jira references.

    Args:
        description: PR description (typically last commit message)
        ticket: Main Jira ticket dict with 'key' and 'summary'
        jira_url: Jira server URL
        epic: Optional epic dict with 'key' and 'summary'
        linked_issues: Optional list of linked issue dicts
        additional_tickets: Optional list of additional ticket dicts with 'key' and 'summary'

    Returns:
        Formatted PR body markdown
    """
    lines = []

    # Description section
    lines.append("## Description")
    lines.append("")
    lines.append(description.strip())
    lines.append("")

    # Jira References section
    lines.append("## Jira References")
    lines.append("")

    # Main ticket
    ticket_url = f"{jira_url}/browse/{ticket['key']}"
    lines.append(f"- **Ticket:** [{ticket['key']}]({ticket_url}) - {ticket['summary']}")

    # Additional tickets
    if additional_tickets:
        for add_ticket in additional_tickets:
            add_url = f"{jira_url}/browse/{add_ticket['key']}"
            lines.append(
                f"- **Ticket:** [{add_ticket['key']}]({add_url}) - {add_ticket['summary']}"
            )

    # Epic (if exists)
    if epic:
        epic_url = f"{jira_url}/browse/{epic['key']}"
        lines.append(f"- **Epic:** [{epic['key']}]({epic_url}) - {epic['summary']}")

    lines.append("")

    # Related/Linked Issues section
    if linked_issues:
        lines.append("## Related Issues")
        lines.append("")
        for issue in linked_issues:
            issue_url = f"{jira_url}/browse/{issue['key']}"
            direction = issue.get("direction", issue.get("link_type", "related to"))
            lines.append(
                f"- [{issue['key']}]({issue_url}) - {issue['summary']} ({direction})"
            )
        lines.append("")

    return "\n".join(lines)


def format_pr_title(
    ticket_key: str,
    summary: str,
    additional_keys: list[str] | None = None,
) -> str:
    """Format PR title with ticket reference.

    Args:
        ticket_key: Jira ticket key (e.g., PROJ-123)
        summary: Ticket summary/title
        additional_keys: Optional list of additional ticket keys

    Returns:
        Formatted PR title like "[PROJ-123] - Summary"
        or "[PROJ-123 - PROJ-456] - Summary" with additional tickets
    """
    if additional_keys:
        prefix = " - ".join([ticket_key, *additional_keys])
    else:
        prefix = ticket_key

    # Truncate summary if too long (GitHub recommends < 72 chars)
    max_summary_len = 60 - len(prefix) - 5  # account for "[] - " and buffer
    if len(summary) > max_summary_len:
        summary = summary[: max_summary_len - 3] + "..."

    return f"[{prefix}] - {summary}"

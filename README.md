# jh

**j**ira + g**h** = **jh**

A CLI tool that integrates GitHub CLI with Jira for creating PRs with automatic Jira ticket references.

## Installation

### uv (recommended)

```bash
uv tool install .
```

### pip (editable)

```bash
pip install -e .
```

### pipx

```bash
pipx install .
```

### Development

```bash
uv sync
```

This installs in a project-local `.venv`. Run with `uv run jh`.

## Usage

### Authentication

Login to Jira (credentials stored securely in system keyring):

```bash
jh login
```

You'll be prompted for:
- **Jira server URL**: e.g., `https://yourcompany.atlassian.net`
- **Email**: Your Atlassian account email
- **API token**: Generate one at https://id.atlassian.com/manage-profile/security/api-tokens

The token inherits your account permissions. The tool only needs **read access** to:
- Issues (to fetch ticket details)
- Issue links (to fetch related issues)
- Projects (to read epic/parent info)

Credentials are stored in your system's secure keyring:
- macOS: Keychain
- Windows: Credential Manager
- Linux: Secret Service (libsecret/GNOME Keyring)

Check authentication status:

```bash
jh status
```

### Creating PRs

Create a branch with a Jira ticket ID prefix:

```bash
git checkout -b PROJ-123-add-feature
```

Make your changes and commit, then create a PR:

```bash
jh pr
```

The PR will include:
- Title from Jira ticket summary
- Description from last commit message
- Links to Jira ticket, epic, and related issues

Options:

```bash
jh pr --dry-run          # Preview without creating
jh pr --title "Custom"   # Override title
jh pr --no-push          # Don't push branch first
jh pr --base develop     # Target specific base branch
```

## Development

Install dev dependencies:

```bash
uv sync --all-extras
```

Set up pre-commit hooks:

```bash
uv run pre-commit install
```

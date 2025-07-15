<div align="center">
  <img src="Instant Agent.png" alt="Instant Agents Banner" width="600">
</div>

# instant-agent

Examples of how to build remarkably simple agents.

## Installation

### Local Development

```bash
poetry install
```

### Global Installation (Recommended: pipx)

First install `pipx` if you don't have it:
```bash
pip install pipx
```

Then install instant-agent globally:
```bash
# Fresh install
pipx install .

# Force install (removes any existing installation)
pipx install . --force

# Editable install for development
pipx install . --editable

# Upgrade existing installation
pipx upgrade instant-agent
```

### Managing Global Installation
```bash
# Complete cleanup (removes all traces)
pipx uninstall instant-agent
pip uninstall instant-agent  # Remove any pip-installed versions
which instant-agent  # Should show "not found"

# If instant-agent still exists, find and remove manually:
which instant-agent  # Note the path
rm $(which instant-agent)  # Remove the binary

# Clean pipx cache and reinstall
pipx list  # Verify instant-agent not listed
pipx install . --force  # Fresh install

# Verify clean installation
which instant-agent  # Should show pipx path
instant-agent --help  # Test it works
```

### Troubleshooting Installation Issues
If you have installation conflicts:
```bash
# Nuclear option - clean everything
pipx uninstall instant-agent
pip uninstall instant-agent
pip uninstall instant-agents  # Check both names

# Clear any cached wheels
rm -rf dist/ build/ *.egg-info/

# Fresh build and install
poetry build
pipx install . --force
```


**Installation Process:**

```bash
# Method 1: Simple install (recommended)
pipx install . --force

# Method 2: Install with automatic .env copying
python install_with_env.py
```

**Usage:** After installation, `instant-agent` will look for `.env` files in this order:
1. Current working directory (most common)
2. Package installation directory (if copied during install)
3. Creates a template if none found

```bash
# Run from any directory with a .env file
cd /path/to/your/project
instant-agent

# Or run from this project directory
instant-agent
```

## Usage

### Run Locally (Development)

```bash
# Build and run locally for development
poetry build
poetry run python agent/cli.py
```

### Run Globally (after global install)

```bash
instant-agent
```

### Features

- **Intelligent execution**: Automatically decides between simple responses and complex multi-step planning
- **Memory persistence**: Learns from successes and failures across sessions
- **Trial-and-error execution**: Auto-retry with replanning when steps fail
- **Unix-native**: Uses standard command-line tools efficiently
- **Conversation history**: Maintains context across interactions

### Commands

- `clear` - Reset conversation history
- `history` - Show message count
- `quit` / `exit` / `q` - Exit the CLI

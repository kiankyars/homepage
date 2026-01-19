# Outreach Funnel

Minimal funnel for finding and contacting Bay Area investors and frontier lab folks for run invites.

## Setup

```bash
uv sync
```

## Usage

### Import from CSV files (auto-generates emails)
```bash
uv run python outreach.py import people/openai.csv
uv run python outreach.py import people/a16z.csv
```

### Add contacts manually
```bash
uv run python outreach.py add "John Doe" "a16z" "Partner" "https://linkedin.com/in/johndoe"
```

### List contacts
```bash
uv run python outreach.py list
uv run python outreach.py list --uncontacted
```

### Find emails (guesses patterns for existing contacts)
```bash
uv run python outreach.py find-emails
```

### Send email to one contact
```bash
export SMTP_EMAIL="your@gmail.com"
export SMTP_PASSWORD="your-app-password"
uv run python outreach.py send 0 "Running at Mission Bay"
```

### Send emails to all uncontacted contacts (bulk)
```bash
export SMTP_EMAIL="your@gmail.com"
export SMTP_PASSWORD="your-app-password"

# Dry run first (recommended)
uv run python outreach.py send-all --dry-run

# Customize location, day, time
uv run python outreach.py send-all --location "Golden Gate Park" --day "Friday" --time "7am"

# Actually send
uv run python outreach.py send-all
```

The email template format:
```
Hey #firstName#, I'll be running at Mission Bay this Wednesday at 8am.
Feel free to join, I'll be there anyway.
```

## Data Storage

Contacts are stored in `contacts.csv` with columns:
- name, company, role, location, source_url, email, contacted, response, notes

## Email Patterns

The script uses company-specific email patterns based on research:

- **OpenAI**: `first.last@openai.com` (88% most common)
- **a16z**: `first@a16z.com` (55%) or `first_initial+last@a16z.com` (25%)
- **Anthropic**: `first_initial+last@anthropic.com` (75% most common)
- **Others**: Generic patterns (first.last, first_initial+last, etc.)

## LinkedIn Search (Optional)

Search for people directly on LinkedIn without third-party services:

```bash
export LINKEDIN_USERNAME="your@email.com"
export LINKEDIN_PASSWORD="your-password"

# Search for investors at a16z
uv run python outreach.py search-linkedin "investor partner" --company "a16z" --limit 20

# Search for engineers at OpenAI
uv run python outreach.py search-linkedin "engineer" --company "OpenAI" --location "San Francisco Bay Area"
```

**Note:** LinkedIn scraping may violate their Terms of Service. Use responsibly and at your own risk. The `linkedin-api` library uses HTTP requests (not official API) and may break if LinkedIn changes their system.

## Supported Organizations

- a16z / Andreessen Horowitz
- OpenAI
- Anthropic
- Thinking Machines
- General Intuition
- Sequoia
- Accel
- Greylock

Add more in `TARGET_ORGS` dict in `outreach.py`.

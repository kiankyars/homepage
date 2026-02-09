#!/usr/bin/env python3
"""
Minimal funnel for finding and contacting Bay Area investors and frontier lab folks.
"""
import csv
import json
import os
import re
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import List, Dict, Optional
from email_validator import validate_email, EmailNotValidError


# Target organizations
TARGET_ORGS = {
    "a16z": ["a16z.com", "andreessenhorowitz.com"],
    "openai": ["openai.com"],
    "anthropic": ["anthropic.com"],
    "thinking-machines": ["thinkingmachines.ai"],
    "general-intuition": ["generalintuition.com"],
    "sequoia": ["sequoia.com"],
    "accel": ["accel.com"],
    "greylock": ["greylock.com"],
}


def guess_email(name: str, domain: str, company: str = "") -> List[str]:
    """Generate company-specific email patterns from name and domain."""
    # Normalize name - handle cases like "John D." or "Christina (Cas) Y. Li"
    name_clean = re.sub(r'\([^)]+\)', '', name)  # Remove parentheticals
    parts = [p.strip('.') for p in name_clean.lower().strip().split() if p.strip('.')]
    if len(parts) < 1:
        return []
    
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    first_initial = first[0] if first else ""
    last_initial = last[0] if last else ""
    
    company_lower = company.lower() if company else ""
    
    # Company-specific patterns based on research
    if "openai" in company_lower or domain == "openai.com":
        # OpenAI: first.last@openai.com (88% most common)
        patterns = [
            f"{first}.{last}@{domain}" if last else "",
            f"{last}.{first_initial}@{domain}" if last and first_initial else "",
            f"{last}{first_initial}@{domain}" if last and first_initial else "",
        ]
    elif "a16z" in company_lower or "andreessen" in company_lower or domain == "a16z.com":
        # a16z: first@a16z.com (55%) or first_initial+last@a16z.com (25%)
        patterns = [
            f"{first}@{domain}",
            f"{first_initial}{last}@{domain}" if last else "",
            f"{last}@{domain}" if last else "",
            f"{first}{last_initial}@{domain}" if last_initial else "",
        ]
    elif "anthropic" in company_lower or domain == "anthropic.com":
        # Anthropic: first_initial+last@anthropic.com (75% most common)
        patterns = [
            f"{first_initial}{last}@{domain}" if last else "",
            f"{last}@{domain}" if last else "",
            f"{last}-{first_initial}@{domain}" if last and first_initial else "",
        ]
    else:
        # Generic patterns for other companies
        patterns = [
            f"{first}.{last}@{domain}" if last else "",
            f"{first_initial}{last}@{domain}" if last else "",
            f"{first}@{domain}",
            f"{last}@{domain}" if last else "",
        ]
    
    # Filter out empty patterns
    return [p for p in patterns if p and validate_email_address(p)]


def validate_email_address(email: str) -> bool:
    """Basic email validation."""
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def find_domain(company: str) -> Optional[str]:
    """Find domain for a company name."""
    company_lower = company.lower().strip()
    
    for org, domains in TARGET_ORGS.items():
        if org.replace("-", " ") in company_lower or any(
            d.replace(".com", "").replace(".ai", "") in company_lower 
            for d in domains
        ):
            return domains[0]
    
    # Try to infer from company name
    if "a16z" in company_lower or "andreessen" in company_lower:
        return "a16z.com"
    elif "openai" in company_lower:
        return "openai.com"
    elif "anthropic" in company_lower:
        return "anthropic.com"
    
    return None


class OutreachFunnel:
    def __init__(self, data_file: str = "contacts.csv"):
        self.data_file = Path(data_file)
        self.contacts: List[Dict] = []
        self.load_contacts()
    
    def load_contacts(self):
        """Load contacts from CSV."""
        if self.data_file.exists():
            with open(self.data_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.contacts = list(reader)
        else:
            # Initialize with headers
            self.contacts = []
    
    def save_contacts(self):
        """Save contacts to CSV."""
        if not self.contacts:
            return
        
        fieldnames = ["name", "company", "role", "location", "source_url", "email", "contacted", "response", "notes"]
        with open(self.data_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.contacts)
    
    def add_contact(self, name: str, company: str, role: str = "", location: str = "Bay Area", source_url: str = ""):
        """Add a new contact."""
        contact = {
            "name": name,
            "company": company,
            "role": role,
            "location": location,
            "source_url": source_url,
            "email": "",
            "contacted": "no",
            "response": "",
            "notes": "",
        }
        self.contacts.append(contact)
        self.save_contacts()
        return contact
    
    def find_email(self, contact: Dict) -> Optional[str]:
        """Find email for a contact."""
        if contact.get("email"):
            return contact["email"]
        
        domain = find_domain(contact["company"])
        if not domain:
            return None
        
        patterns = guess_email(contact["name"], domain, contact.get("company", ""))
        # Return the first valid pattern (they're ordered by likelihood)
        return patterns[0] if patterns else None
    
    def update_email(self, contact_idx: int, email: str):
        """Update email for a contact."""
        if contact_idx < len(self.contacts):
            self.contacts[contact_idx]["email"] = email
            self.save_contacts()
    
    def list_contacts(self, filter_contacted: bool = False):
        """List all contacts."""
        contacts = self.contacts if not filter_contacted else [
            c for c in self.contacts if c.get("contacted", "no").lower() != "yes"
        ]
        
        for i, contact in enumerate(contacts):
            email = contact.get("email") or "Not found"
            contacted = contact.get("contacted", "no")
            print(f"{i}: {contact['name']} ({contact['company']}) - {email} [{contacted}]")
    
    def send_email(
        self,
        contact_idx: int,
        subject: str,
        body: str,
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 587,
        sender_email: str = "",
        sender_password: str = "",
        dry_run: bool = False,
    ):
        """Send email to a contact."""
        if contact_idx >= len(self.contacts):
            print(f"Invalid contact index: {contact_idx}")
            return False
        
        contact = self.contacts[contact_idx]
        email = contact.get("email")
        
        if not email:
            print(f"No email found for {contact['name']}")
            return False
        
        if dry_run:
            print(f"[DRY RUN] Would send to {contact['name']} ({email})")
            print(f"Subject: {subject}")
            print(f"Body:\n{body}\n")
            return True
        
        if not sender_email or not sender_password:
            print("SMTP credentials required. Set sender_email and sender_password.")
            return False
        
        try:
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            
            contact["contacted"] = "yes"
            self.save_contacts()
            print(f"✓ Email sent to {contact['name']} ({email})")
            return True
        except Exception as e:
            print(f"✗ Error sending email to {contact['name']}: {e}")
            return False
    
    def send_bulk(
        self,
        subject: str = "Running at Mission Bay",
        location: str = "Mission Bay",
        day: str = "Wednesday",
        run_time: str = "8am",
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 587,
        sender_email: str = "",
        sender_password: str = "",
        dry_run: bool = False,
        filter_contacted: bool = True,
        company_filter: str = "",
    ):
        """Send emails to all uncontacted contacts."""
        import time as time_module  # Import at top to avoid shadowing
        
        company_query = company_filter.strip().lower()
        contacts_to_send = [
            (i, c) for i, c in enumerate(self.contacts)
            if c.get("email") and (not filter_contacted or c.get("contacted", "no").lower() != "yes")
            and (not company_query or company_query in (c.get("company") or "").strip().lower())
        ]
        
        if not contacts_to_send:
            print("No contacts to send emails to.")
            return
        
        print(f"Sending to {len(contacts_to_send)} contact(s)...")
        if dry_run:
            print("[DRY RUN MODE - No emails will actually be sent]\n")
        
        success_count = 0
        for idx, contact in contacts_to_send:
            body = generate_run_invite(contact, location=location, day=day, run_time=run_time)
            if self.send_email(
                idx, subject, body,
                smtp_server=smtp_server, smtp_port=smtp_port,
                sender_email=sender_email, sender_password=sender_password,
                dry_run=dry_run
            ):
                success_count += 1
            # Small delay to avoid rate limiting
            if not dry_run:
                time_module.sleep(1)
        
        print(f"\nSent {success_count}/{len(contacts_to_send)} emails successfully.")


def search_hunter_domain(
    domain: str,
    api_key: str = "",
    company: str = "",
    limit: int = 25,
) -> List[Dict]:
    """Search Hunter.io for emails at a domain."""
    if not api_key:
        api_key = os.getenv("HUNTER_API_KEY", "")
    if not api_key:
        print("Hunter API key required. Set HUNTER_API_KEY env var.")
        return []
    if not domain:
        print("Domain required for Hunter search.")
        return []
    response = requests.get(
        "https://api.hunter.io/v2/domain-search",
        params={"domain": domain, "api_key": api_key, "limit": limit},
        timeout=20,
    )
    if response.status_code != 200:
        print(f"Hunter API error: {response.status_code} {response.text}")
        return []
    payload = response.json()
    data = payload.get("data", {})
    org_name = company or data.get("organization", "") or domain
    contacts: List[Dict] = []
    for entry in data.get("emails", []):
        email = (entry.get("value") or "").strip()
        if not email or not validate_email_address(email):
            continue
        first = (entry.get("first_name") or "").strip()
        last = (entry.get("last_name") or "").strip()
        name = " ".join([first, last]).strip() or entry.get("value", "")
        role = (entry.get("position") or "").strip()
        location = (entry.get("location") or "").strip()
        confidence = entry.get("confidence", "")
        notes = f"hunter_confidence:{confidence}" if confidence != "" else "hunter"
        contacts.append({
            "name": name,
            "company": org_name,
            "role": role,
            "location": location,
            "source_url": entry.get("linkedin", "") or "https://hunter.io",
            "email": email,
            "contacted": "no",
            "response": "",
            "notes": notes,
        })
    return contacts


def import_from_csv(csv_path: str, company: str = "") -> List[Dict]:
    """Import contacts from a CSV file (like the ones from people/ directory)."""
    contacts = []
    path = Path(csv_path)
    
    if not path.exists():
        print(f"File not found: {csv_path}")
        return contacts
    
    # Infer company from filename if not provided
    if not company:
        filename = path.stem.lower()
        if "a16z" in filename or "andreessen" in filename:
            company = "a16z"
        elif "openai" in filename:
            company = "openai"
        elif "anthropic" in filename:
            company = "anthropic"
        else:
            company = filename
    
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip empty rows or footer rows
            if not row.get("name") or not row["name"].strip():
                continue
            if "Export limit" in row.get("name", "") or "Upgrade" in row.get("name", ""):
                continue
            
            name = row.get("name", "").strip()
            role = row.get("jobTitle", "").strip()
            source_url = row.get("profileUrl", "").strip()
            
            if name:
                contacts.append({
                    "name": name,
                    "company": company,
                    "role": role,
                    "location": "Bay Area",
                    "source_url": source_url,
                    "email": "",
                    "contacted": "no",
                    "response": "",
                    "notes": "",
                })
    
    return contacts


def import_linkedin_export(csv_path: str, company: str = "") -> List[Dict]:
    """Import contacts from a LinkedIn connections export CSV."""
    contacts = []
    path = Path(csv_path)
    
    if not path.exists():
        print(f"File not found: {csv_path}")
        return contacts
    
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "First Name" in row:
                first = row.get("First Name", "").strip()
                last = row.get("Last Name", "").strip()
                name = f"{first} {last}".strip()
                role = row.get("Position", "").strip()
                company_name = row.get("Company", "").strip() or company
                source_url = row.get("URL", "").strip()
                email = row.get("Email Address", "").strip()
                location = "Bay Area"
            else:
                name = row.get("fullName", "").strip()
                role = row.get("jobTitle", "").strip()
                company_name = row.get("company", "").strip() or company
                source_url = row.get("profileUrl", "").strip()
                location = row.get("location", "").strip() or "Bay Area"
                email = ""
                additional_info = row.get("additionalInfo", "").strip()
                if additional_info:
                    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", additional_info)
                    if match:
                        email = match.group(0)
            
            if not name:
                continue
            contacts.append({
                "name": name,
                "company": company_name,
                "role": role,
                "location": location,
                "source_url": source_url,
                "email": email if validate_email_address(email) else "",
                "contacted": "no",
                "response": "",
                "notes": "",
            })
    
    return contacts


def upsert_contacts(funnel: "OutreachFunnel", contacts: List[Dict]) -> int:
    """Append contacts and persist; return added count."""
    if not contacts:
        return 0
    def contact_key(contact: Dict) -> str:
        email = (contact.get("email") or "").strip().lower()
        if email:
            return f"email:{email}"
        source_url = (contact.get("source_url") or "").strip().lower()
        if source_url:
            return f"url:{source_url}"
        name = (contact.get("name") or "").strip().lower()
        company = (contact.get("company") or "").strip().lower()
        return f"name:{name}|company:{company}"

    existing_keys = {contact_key(c) for c in funnel.contacts if c}
    added = 0
    for contact in contacts:
        key = contact_key(contact)
        if key in existing_keys:
            continue
        funnel.contacts.append(contact)
        existing_keys.add(key)
        added += 1
    if added:
        funnel.save_contacts()
    return added


def filter_contacts_by_company(contacts: List[Dict], company_query: str) -> List[Dict]:
    """Filter contacts by company name substring (case-insensitive)."""
    if not company_query:
        return contacts
    query = company_query.strip().lower()
    return [
        c for c in contacts
        if query in (c.get("company") or "").strip().lower()
    ]


def dedupe_contacts(funnel: "OutreachFunnel") -> int:
    """Remove duplicate contacts, keeping best data; return removed count."""
    def contact_key(contact: Dict) -> str:
        email = (contact.get("email") or "").strip().lower()
        if email:
            return f"email:{email}"
        source_url = (contact.get("source_url") or "").strip().lower()
        if source_url:
            return f"url:{source_url}"
        name = (contact.get("name") or "").strip().lower()
        company = (contact.get("company") or "").strip().lower()
        return f"name:{name}|company:{company}"

    def better_contact(a: Dict, b: Dict) -> Dict:
        """Prefer contacted=yes, email, role, location, source_url, notes."""
        def score(c: Dict) -> int:
            score = 0
            if (c.get("contacted") or "").lower() == "yes":
                score += 10
            if c.get("email"):
                score += 5
            if c.get("role"):
                score += 2
            if c.get("location"):
                score += 1
            if c.get("source_url"):
                score += 1
            if c.get("notes"):
                score += 1
            return score
        return a if score(a) >= score(b) else b

    seen: Dict[str, Dict] = {}
    original_count = len(funnel.contacts)
    for contact in funnel.contacts:
        key = contact_key(contact)
        if key in seen:
            seen[key] = better_contact(seen[key], contact)
        else:
            seen[key] = contact
    funnel.contacts = list(seen.values())
    removed = original_count - len(funnel.contacts)
    if removed > 0:
        funnel.save_contacts()
    return removed


def generate_emails_for_range(funnel: "OutreachFunnel", start_idx: int, count: int):
    """Generate and store emails for a contiguous range of contacts."""
    end_idx = start_idx + count
    for i in range(start_idx, end_idx):
        contact = funnel.contacts[i]
        email = funnel.find_email(contact)
        if email:
            funnel.update_email(i, email)
            print(f"  {contact['name']}: {email}")


def get_first_name(full_name: str) -> str:
    """Extract first name from full name, handling edge cases."""
    if not full_name:
        return "there"
    # Remove parentheticals and extra info
    name_clean = re.sub(r'\([^)]+\)', '', full_name)
    parts = name_clean.strip().split()
    if not parts:
        return "there"
    return parts[0]


def generate_run_invite(
    contact: Dict,
    location: str = "Mission Bay",
    day: str = "Wednesday",
    run_time: str = "8am"
) -> str:
    """Generate a personalized run invite email using the template format."""
    first_name = get_first_name(contact["name"])
    
    template = f"""Hey {first_name}, I'll be running at {location} this {day} at {run_time}.
Feel free to join, I'll be there anyway.
"""
    return template


if __name__ == "__main__":
    import sys
    
    funnel = OutreachFunnel()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python outreach.py add <name> <company> [role] [source_url]")
        print("  python outreach.py import <csv_file> [company]")
        print("  python outreach.py import-linkedin-export <csv_file> [company]")
        print("  python outreach.py search-hunter <domain> [--company COMPANY] [--limit N]")
        print("  python outreach.py list")
        print("  python outreach.py find-emails")
        print("  python outreach.py send <index> [subject] [body_file]")
        print("  python outreach.py send-all [--dry-run] [--location LOCATION] [--day DAY] [--time TIME]")
        print("  python outreach.py run-anthropic [--linkedin-export CSV] [--hunter] [--limit N] [--dry-run] [--subject SUBJECT]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "add":
        if len(sys.argv) < 4:
            print("Usage: python outreach.py add <name> <company> [role] [source_url]")
            sys.exit(1)
        name = sys.argv[2]
        company = sys.argv[3]
        role = sys.argv[4] if len(sys.argv) > 4 else ""
        source_url = sys.argv[5] if len(sys.argv) > 5 else ""
        funnel.add_contact(name, company, role, source_url=source_url)
        print(f"Added: {name} at {company}")
    
    elif command == "import":
        if len(sys.argv) < 3:
            print("Usage: python outreach.py import <csv_file> [company]")
            sys.exit(1)
        csv_file = sys.argv[2]
        company = sys.argv[3] if len(sys.argv) > 3 else ""
        contacts = import_from_csv(csv_file, company)
        added_count = upsert_contacts(funnel, contacts)
        print(f"Imported {len(contacts)} contacts from {csv_file}")
        # Auto-generate emails for imported contacts
        print("Generating emails...")
        generate_emails_for_range(funnel, len(funnel.contacts) - added_count, added_count)
    
    elif command == "import-linkedin-export":
        if len(sys.argv) < 3:
            print("Usage: python outreach.py import-linkedin-export <csv_file> [company]")
            sys.exit(1)
        
        csv_file = sys.argv[2]
        company = sys.argv[3] if len(sys.argv) > 3 else ""
        contacts = import_linkedin_export(csv_file, company)
        added_count = upsert_contacts(funnel, contacts)
        print(f"Imported {added_count} contacts from {csv_file}")
        print("Generating emails...")
        generate_emails_for_range(funnel, len(funnel.contacts) - added_count, added_count)
    
    elif command == "search-hunter":
        if len(sys.argv) < 3:
            print("Usage: python outreach.py search-hunter <domain> [--company COMPANY] [--limit N]")
            sys.exit(1)
        
        domain = sys.argv[2]
        company = ""
        limit = 25
        
        if "--company" in sys.argv:
            idx = sys.argv.index("--company")
            if idx + 1 < len(sys.argv):
                company = sys.argv[idx + 1]
        
        if "--limit" in sys.argv:
            idx = sys.argv.index("--limit")
            if idx + 1 < len(sys.argv):
                limit = int(sys.argv[idx + 1])
        
        contacts = search_hunter_domain(domain, company=company, limit=limit)
        if contacts:
            added_count = upsert_contacts(funnel, contacts)
            print(f"Added {len(contacts)} contacts from Hunter domain search")
            # Auto-generate emails
            print("Generating emails...")
            generate_emails_for_range(funnel, len(funnel.contacts) - added_count, added_count)
        else:
            print("No contacts found or error occurred.")
    
    elif command == "list":
        filter_contacted = "--uncontacted" in sys.argv
        funnel.list_contacts(filter_contacted=filter_contacted)
    
    elif command == "find-emails":
        for i, contact in enumerate(funnel.contacts):
            if not contact.get("email"):
                email = funnel.find_email(contact)
                if email:
                    funnel.update_email(i, email)
                    print(f"Found email for {contact['name']}: {email}")
                else:
                    print(f"No email found for {contact['name']}")
    
    elif command == "send":
        if len(sys.argv) < 3:
            print("Usage: python outreach.py send <index> [subject] [body_file]")
            sys.exit(1)
        
        idx = int(sys.argv[2])
        subject = sys.argv[3] if len(sys.argv) > 3 else "Quick question about a run in SF"
        body_file = sys.argv[4] if len(sys.argv) > 4 else None
        
        contact = funnel.contacts[idx]
        
        if body_file and Path(body_file).exists():
            with open(body_file, "r") as f:
                body = f.read()
        else:
            body = generate_run_invite(contact)
        
        # Support template variables in body_file content
        if body_file and Path(body_file).exists():
            first_name = get_first_name(contact["name"])
            body = body.replace("#firstName#", first_name)
        
        # Get credentials from environment or prompt
        import os
        sender_email = os.getenv("SMTP_EMAIL", "")
        sender_password = os.getenv("SMTP_PASSWORD", "")
        
        if not sender_email or not sender_password:
            print("Set SMTP_EMAIL and SMTP_PASSWORD environment variables")
            print("Or edit the script to hardcode (not recommended)")
            sys.exit(1)
        
        funnel.send_email(idx, subject, body, sender_email=sender_email, sender_password=sender_password)
    
    elif command == "send-all":
        import os
        dry_run = "--dry-run" in sys.argv
        sender_email = os.getenv("SMTP_EMAIL", "")
        sender_password = os.getenv("SMTP_PASSWORD", "")
        
        if not dry_run and (not sender_email or not sender_password):
            print("Set SMTP_EMAIL and SMTP_PASSWORD environment variables")
            sys.exit(1)
        
        # Parse optional arguments
        dry_run = "--dry-run" in sys.argv
        location = "Mission Bay"
        day = "Wednesday"
        run_time = "8am"
        subject = "Running at Mission Bay"
        
        if "--location" in sys.argv:
            idx = sys.argv.index("--location")
            if idx + 1 < len(sys.argv):
                location = sys.argv[idx + 1]
        
        if "--day" in sys.argv:
            idx = sys.argv.index("--day")
            if idx + 1 < len(sys.argv):
                day = sys.argv[idx + 1]
        
        if "--time" in sys.argv:
            idx = sys.argv.index("--time")
            if idx + 1 < len(sys.argv):
                run_time = sys.argv[idx + 1]
        
        if "--subject" in sys.argv:
            idx = sys.argv.index("--subject")
            if idx + 1 < len(sys.argv):
                subject = sys.argv[idx + 1]
        
        funnel.send_bulk(
            subject=subject,
            location=location,
            day=day,
            run_time=run_time,
            sender_email=sender_email,
            sender_password=sender_password,
            dry_run=dry_run,
        )

    elif command == "run-anthropic":
        import os
        dry_run = "--dry-run" in sys.argv
        subject = "Run in Mission Bay this Wednesday?"
        linkedin_export = ""
        limit = 25
        use_hunter = "--hunter" in sys.argv
        if "--subject" in sys.argv:
            idx = sys.argv.index("--subject")
            if idx + 1 < len(sys.argv):
                subject = sys.argv[idx + 1]
        if "--linkedin-export" in sys.argv:
            idx = sys.argv.index("--linkedin-export")
            if idx + 1 < len(sys.argv):
                linkedin_export = sys.argv[idx + 1]
        if "--limit" in sys.argv:
            idx = sys.argv.index("--limit")
            if idx + 1 < len(sys.argv):
                limit = int(sys.argv[idx + 1])
        sender_email = os.getenv("SMTP_EMAIL", "")
        sender_password = os.getenv("SMTP_PASSWORD", "")
        if not dry_run and (not sender_email or not sender_password):
            print("Set SMTP_EMAIL and SMTP_PASSWORD environment variables")
            sys.exit(1)
        start_idx = len(funnel.contacts)
        contacts = import_from_csv("people/anthropic.csv", "anthropic")
        added_count = upsert_contacts(funnel, contacts)
        print(f"Imported {added_count} contacts from people/anthropic.csv")
        if added_count:
            generate_emails_for_range(funnel, start_idx, added_count)
        if linkedin_export:
            start_idx = len(funnel.contacts)
            linkedin_contacts = import_linkedin_export(linkedin_export, "anthropic")
            linkedin_contacts = filter_contacts_by_company(linkedin_contacts, "anthropic")
            added_from_linkedin = upsert_contacts(funnel, linkedin_contacts)
            print(f"Imported {added_from_linkedin} contacts from LinkedIn export")
            if added_from_linkedin:
                generate_emails_for_range(funnel, start_idx, added_from_linkedin)
        if use_hunter:
            start_idx = len(funnel.contacts)
            hunter_contacts = search_hunter_domain(
                "anthropic.com",
                company="anthropic",
                limit=limit,
            )
            added_from_hunter = upsert_contacts(funnel, hunter_contacts)
            print(f"Added {added_from_hunter} contacts from Hunter domain search")
            if added_from_hunter:
                generate_emails_for_range(funnel, start_idx, added_from_hunter)
        removed = dedupe_contacts(funnel)
        if removed:
            print(f"Removed {removed} duplicate contacts from contacts.csv")
        funnel.send_bulk(
            subject=subject,
            sender_email=sender_email,
            sender_password=sender_password,
            dry_run=dry_run,
            company_filter="anthropic",
        )
    
    else:
        print(f"Unknown command: {command}")

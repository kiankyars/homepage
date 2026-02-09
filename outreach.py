#!/usr/bin/env python3
"""Minimal email sender for company contact lists in ./contacts.

CSV format: first,last[,email]
If email is missing, a company-specific pattern is used.
"""
import argparse
import csv
import os
import smtplib
import time
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, Iterable, List, Optional

CONTACTS_DIR = Path("contacts")

COMPANY_CONFIG = {
    "openai": {
        "domain": "openai.com",
        "pattern": "{first}.{last}@{domain}",
    },
    "anthropic": {
        "domain": "anthropic.com",
        "pattern": "{first_initial}{last}@{domain}",
    },
    "a16z": {
        "domain": "a16z.com",
        "pattern": "{first}@{domain}",
    },
    "thinking_machines_lab": {
        "domain": "thinkingmachines.ai",
        "pattern": "{first}.{last}@{domain}",
    },
}


@dataclass
class Contact:
    first: str
    last: str
    email: str


def normalize(s: str) -> str:
    return (s or "").strip()


def load_contacts(company: str) -> List[Contact]:
    path = CONTACTS_DIR / f"{company}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing contacts file: {path}")

    contacts: List[Contact] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            first = normalize(row.get("first", ""))
            last = normalize(row.get("last", ""))
            email = normalize(row.get("email", ""))
            if not first:
                continue
            contacts.append(Contact(first=first, last=last, email=email))
    return contacts


def render_email(contact: Contact, company: str, pattern_override: Optional[str]) -> Optional[str]:
    if contact.email:
        return contact.email
    cfg = COMPANY_CONFIG.get(company)
    if not cfg:
        return None
    domain = cfg["domain"]
    pattern = pattern_override or cfg["pattern"]
    first = contact.first.lower()
    last = contact.last.lower()
    first_initial = first[0] if first else ""
    if "{last}" in pattern and not last:
        return None
    return pattern.format(
        first=first,
        last=last,
        first_initial=first_initial,
        domain=domain,
    )


def build_body(template: str, contact: Contact, company: str) -> str:
    return template.format(
        first=contact.first,
        last=contact.last,
        company=company,
    )


def send_email(
    smtp_server: str,
    smtp_port: int,
    sender_email: str,
    sender_password: str,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)


def iter_companies(all_companies: bool, company: Optional[str]) -> Iterable[str]:
    if all_companies:
        return sorted(COMPANY_CONFIG.keys())
    if not company:
        raise ValueError("Provide --company or use --all")
    return [company]


def main() -> int:
    parser = argparse.ArgumentParser(description="Send emails to contacts in ./contacts")
    parser.add_argument("--company", help="Company key (e.g., openai)")
    parser.add_argument("--all", action="store_true", help="Send to all companies")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--body-file", help="Path to email body template")
    parser.add_argument(
        "--body",
        help="Inline body template (overrides --body-file). Use {first}, {last}, {company}.",
    )
    parser.add_argument("--pattern", help="Override email pattern, e.g. '{first}.{last}@{domain}'")
    parser.add_argument("--dry-run", action="store_true", help="Do not send, just print")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between sends")
    parser.add_argument("--smtp-server", default="smtp.gmail.com")
    parser.add_argument("--smtp-port", type=int, default=587)
    args = parser.parse_args()

    sender_email = os.getenv("SMTP_EMAIL", "")
    sender_password = os.getenv("SMTP_PASSWORD", "")
    if not args.dry_run and (not sender_email or not sender_password):
        print("Set SMTP_EMAIL and SMTP_PASSWORD environment variables")
        return 1

    if args.body:
        template = args.body
    elif args.body_file:
        template = Path(args.body_file).read_text(encoding="utf-8")
    else:
        template = "Hi {first},\n\nQuick hello from my side.\n"

    total_sent = 0
    total_skipped = 0

    for company in iter_companies(args.all, args.company):
        contacts = load_contacts(company)
        for contact in contacts:
            to_email = render_email(contact, company, args.pattern)
            if not to_email:
                total_skipped += 1
                print(f"SKIP {company}: {contact.first} {contact.last} (no email)")
                continue

            body = build_body(template, contact, company)
            if args.dry_run:
                print(f"DRY RUN {company}: {contact.first} {contact.last} <{to_email}>")
                continue

            send_email(
                smtp_server=args.smtp_server,
                smtp_port=args.smtp_port,
                sender_email=sender_email,
                sender_password=sender_password,
                to_email=to_email,
                subject=args.subject,
                body=body,
            )
            total_sent += 1
            if args.sleep:
                time.sleep(args.sleep)

    if args.dry_run:
        print("Dry run complete.")
    else:
        print(f"Sent {total_sent} email(s). Skipped {total_skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Security Policy

## Supported Versions

Security updates are applied only to the latest release on the `main` branch.

## Reporting a Vulnerability

If you discover a security vulnerability in RSVP Reader, please report it
**privately** — do not open a public GitHub issue.

**Preferred:** use GitHub's private vulnerability reporting at
<https://github.com/cortexuvula/RSVP/security/advisories/new>. This keeps the
report visible only to repository maintainers and lets us coordinate a fix and
disclosure together. (If you don't see the option, the repository owner may
need to enable it under *Settings → Security → Code security → Private
vulnerability reporting*.)

**Fallback:** email the maintainer at `cortexpeterpan@gmail.com` with
`[SECURITY] RSVP Reader` in the subject line.

Please include:

- A description of the issue and its potential impact
- Steps to reproduce (code, input, or a URL that triggers it)
- The affected version (see *Help → About* in the app, or `rsvp.__version__`)
- Any suggested fix, if you have one

We aim to acknowledge reports within **72 hours** and to ship a fix or
mitigation for confirmed high-severity issues within **30 days**, coordinated
with the reporter on a disclosure timeline.

## Security-Relevant Attack Surface

RSVP Reader is a desktop application that processes untrusted content. Areas
that receive particular scrutiny:

- **URL fetching** (`rsvp/core/text_processor.py`) — the app fetches
  user-supplied URLs to extract article text. All fetches are SSRF-hardened:
  the scheme is restricted to `http`/`https`, and resolved IP addresses are
  rejected if they fall within private/reserved ranges (loopback, RFC 1918,
  link-local, CG-NAT, and IPv4-mapped IPv6).
- **File parsing** — `.epub`, `.pdf`, `.md`, and `.html` are parsed with
  third-party libraries (`ebooklib`, `pymupdf`, `beautifulsoup4`). Malformed
  or malicious files are handled defensively, but vulnerabilities in those
  upstream parsers are out of scope for this policy; report them upstream.
- **Settings & stats persistence** — written atomically via temp file +
  `os.replace()` to resist corruption from mid-write crashes.

## Scope

In scope: vulnerabilities in RSVP Reader's own code that could compromise a
user's system or data when the app is used as intended.

Out of scope: vulnerabilities requiring the attacker to already control the
user's machine, or bugs in dependencies (report those upstream).

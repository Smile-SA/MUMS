# Security Policy

## Supported versions

Only the latest release is actively maintained.

| Version | Supported |
|---------|-----------|
| latest  | ✓ |
| older   | ✗ |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report security issues by email to the maintainer:
**etienne.leclercq3@gmail.com**

Include:
- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- Any suggested mitigations

You can expect an acknowledgement within 72 hours and a status update within
7 days.

## Scope

This project runs **locally** (Kind clusters on the developer's machine). It is
not designed to be exposed to the public internet. The primary security concerns
are:

- Secrets or credentials accidentally committed to history
- Dependencies with known CVEs
- Shell scripts susceptible to injection via untrusted input

Out of scope: network-level attacks against a deployed instance (the platform is
not a network service).

# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in QGIS FMV, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

### How to report

1. **Email:** Send details to [franka1986@gmail.com](mailto:franka1986@gmail.com)
2. **GitHub Security Advisories:** Use the [private vulnerability reporting](https://github.com/All4Gis/QGISFMV/security/advisories/new) feature

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### What to expect

- **Acknowledgment** within 48 hours
- **Status update** within 7 days
- **Resolution timeline** based on severity

## Scope

This policy covers the QGIS FMV plugin code in this repository. It does not cover:

- **pymisb** (separate project: [pypi.org/project/pymisb](https://pypi.org/project/pymisb/))
- **QGIS** core application
- **FFmpeg** / external dependencies

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest main branch | Yes |
| Older releases | Best-effort |

## Security Best Practices for Users

- Keep QGIS, FFmpeg, and pymisb updated
- Do not open untrusted video files from unknown sources
- Review metadata before operational use (MISB data can be crafted)
- Use the plugin in a sandboxed environment for untrusted content

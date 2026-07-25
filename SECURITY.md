# Security Policy

## Supported versions

Security fixes are provided for the latest tagged release.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository. Do not open a public issue containing credentials, private creator data, browser cookies, or unpublished report content.

## Credential handling

The repository never needs a token for fixture tests or dry-run mode. Real adapters must read credentials from their host environment or secret store. Do not put credentials in `mcp.json.example`, CLI arguments, source files, test fixtures, logs, or generated reports.

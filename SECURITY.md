# Security

## Supported versions

Only the latest release and `main` receive fixes.

## What matters here

Genomes are code written by a language model and executed on your machine. The membrane
(`bio/membrane.py`) is the boundary: no imports, no dunders, a restricted builtins table,
a size cap, and a wall-clock budget. A way for a genome to reach the filesystem, the
network, the interpreter's internals, or the rest of the process is a security bug.
So is any way for `.env` contents to leave the machine other than as the `Authorization`
header to the endpoint you configured.

## Reporting

Report privately through
[GitHub Security Advisories](https://github.com/oddurs/biotic/security/advisories/new).
Do not open a public issue. Include a genome or a sequence of commands that reproduces it.

You will get an acknowledgement within 3 days and a fix or a decision within 14. Credit
goes in the release notes unless you would rather it did not.

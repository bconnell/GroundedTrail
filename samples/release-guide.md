# Release guide

A software release starts with a clean checkout and a reproducible dependency installation. Engineers run unit tests and integration tests before publishing artifacts.

The release checklist requires source and configuration inspection for hardcoded secrets. It also requires confirmation that documented setup steps match the tested build.

A release is complete only when its deployment and rollback instructions have been checked against the candidate artifact. Failed validation prevents publication.

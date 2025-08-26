# src/platform/__init__.py
"""
Package marker for the platform module.

This module encapsulates all tenant-aware functionality such as
configuration storage, caching and rate limiting.  The package follows
the principles of Clean Architecture: domain types live in the
``domain`` subpackage, persistence concerns in ``infrastructure``,
application services in ``application`` and API routing in ``api``.
"""

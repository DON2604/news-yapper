"""Domain errors raised by services and mapped to HTTP responses in app.main."""

from __future__ import annotations


class DomainError(Exception):
    status_code = 400


class NotFoundError(DomainError):
    status_code = 404


class ForbiddenError(DomainError):
    status_code = 403


class ConflictError(DomainError):
    status_code = 409


class InvalidInputError(DomainError):
    status_code = 422

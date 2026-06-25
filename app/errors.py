"""Application error helpers."""

from __future__ import annotations


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def bad_request(code: str, message: str) -> AppError:
    return AppError(400, code, message)


def unauthorized(code: str, message: str) -> AppError:
    return AppError(401, code, message)


def forbidden(code: str, message: str) -> AppError:
    return AppError(403, code, message)


def not_found(code: str, message: str) -> AppError:
    return AppError(404, code, message)


def conflict(code: str, message: str) -> AppError:
    return AppError(409, code, message)

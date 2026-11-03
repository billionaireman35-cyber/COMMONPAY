class CommonPayError(Exception):
    """Base exception for CommonPay application errors."""


class ProviderUnavailable(CommonPayError):
    pass


class ProviderVerificationFailed(CommonPayError):
    pass


class ProviderRequestFailed(CommonPayError):
    pass


class InvalidPayment(CommonPayError):
    pass


class InvalidStateTransition(CommonPayError):
    pass


class IdempotencyConflict(CommonPayError):
    pass


class FinancialInvariantViolation(CommonPayError):
    pass


class AuthorizationDenied(CommonPayError):
    pass

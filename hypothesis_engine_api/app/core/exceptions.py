from fastapi import status as http_status


class HypothesisEngineError(Exception):
    status_code: int = http_status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "An internal error occurred"

    def __init__(self, detail: str | None = None, status_code: int | None = None):
        if detail:
            self.detail = detail
        if status_code:
            self.status_code = status_code
        super().__init__(self.detail)


class NotFoundError(HypothesisEngineError):
    status_code = http_status.HTTP_404_NOT_FOUND
    detail = "Resource not found"


class ValidationError(HypothesisEngineError):
    status_code = 422
    detail = "Validation error"


class InvalidTransitionError(HypothesisEngineError):
    status_code = http_status.HTTP_409_CONFLICT
    detail = "Invalid status transition"

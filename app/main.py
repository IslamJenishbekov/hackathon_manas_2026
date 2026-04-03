from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes.chat import router as chat_router
from app.api.routes.get_info import router as get_info_router
from app.api.routes.save_doc import router as save_doc_router
from app.services.get_info_service import ServiceValidationError, UpstreamServiceError


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
            }
        },
    )


app = FastAPI(title="Hackaton AI 2026", version="0.1.0")
app.include_router(chat_router)
app.include_router(get_info_router)
app.include_router(save_doc_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(ServiceValidationError)
def handle_service_validation_error(
    _request: Request,
    exc: ServiceValidationError,
) -> JSONResponse:
    return error_response(422, "validation_error", str(exc))


@app.exception_handler(RequestValidationError)
def handle_request_validation_error(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    message = "; ".join(error["msg"] for error in exc.errors()) or "request validation failed"
    return error_response(422, "validation_error", message)


@app.exception_handler(UpstreamServiceError)
def handle_upstream_service_error(
    _request: Request,
    exc: UpstreamServiceError,
) -> JSONResponse:
    return error_response(500, "internal_error", str(exc))


@app.exception_handler(Exception)
def handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
    return error_response(500, "internal_error", "unexpected internal error")

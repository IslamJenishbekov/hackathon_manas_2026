from app.api.routes.asr import router as asr_router
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes.chat import router as chat_router
from app.api.routes.fact_of_day import router as fact_of_day_router
from app.api.routes.get_info import router as get_info_router
from app.api.routes.pdf import router as pdf_router
from app.api.routes.save_doc import router as save_doc_router
from app.api.routes.voice import router as voice_router
from app.services.get_info_service import (
    DuplicatePersonError,
    ServiceValidationError,
    UnsupportedMediaTypeError,
    UpstreamServiceError,
)


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    payload: dict[str, object] = {
        "code": code,
        "message": message,
    }
    if details is not None:
        payload["details"] = details
    return JSONResponse(status_code=status_code, content={"error": payload})


app = FastAPI(title="Hackaton AI 2026", version="0.1.0")
app.include_router(chat_router)
app.include_router(fact_of_day_router)
app.include_router(get_info_router)
app.include_router(pdf_router)
app.include_router(save_doc_router)
app.include_router(voice_router)
app.include_router(asr_router)


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


@app.exception_handler(UnsupportedMediaTypeError)
def handle_unsupported_media_type_error(
    _request: Request,
    exc: UnsupportedMediaTypeError,
) -> JSONResponse:
    return error_response(415, "unsupported_media_type", str(exc))


@app.exception_handler(UpstreamServiceError)
def handle_upstream_service_error(
    _request: Request,
    exc: UpstreamServiceError,
) -> JSONResponse:
    return error_response(500, "internal_error", str(exc))


@app.exception_handler(DuplicatePersonError)
def handle_duplicate_person_error(
    _request: Request,
    exc: DuplicatePersonError,
) -> JSONResponse:
    return error_response(
        409,
        "duplicate_person_detected",
        str(exc),
        details={
            "person_id": exc.match.person_id,
            "full_name": exc.match.full_name,
            "normalized_name": exc.match.normalized_name,
            "birth_year": exc.match.birth_year,
            "confidence": round(exc.match.confidence, 4),
            "matched_fields": exc.match.matched_fields,
        },
    )


@app.exception_handler(Exception)
def handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
    return error_response(500, "internal_error", "unexpected internal error")

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routers import auth, monitors
from app.core.config import settings


app = FastAPI(title=settings.app_name)
app.include_router(auth.router)
app.include_router(monitors.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"] if part != "body")
        errors.append(
            {
                "field": field or "request",
                "message": error["msg"],
            }
        )

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Please check the request and try again.",
            "errors": errors,
        },
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

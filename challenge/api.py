import logging
from typing import List

import fastapi
import pandas as pd
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator

from challenge.model import MODEL_PATH, DelayModel

logger = logging.getLogger(__name__)

app = fastapi.FastAPI()

VALID_OPERAS = {
    "Aerolineas Argentinas",
    "Aeromexico",
    "Air Canada",
    "Air France",
    "Alitalia",
    "American Airlines",
    "Austral",
    "Avianca",
    "British Airways",
    "Copa Air",
    "Delta Air",
    "Gol Trans",
    "Grupo LATAM",
    "Iberia",
    "JetSmart SPA",
    "K.L.M.",
    "Lacsa",
    "Latin American Wings",
    "Oceanair Linhas Aereas",
    "Plus Ultra Lineas Aereas",
    "Qantas Airways",
    "Sky Airline",
    "United Airlines",
}
VALID_TIPOS_VUELO = {"I", "N"}
VALID_MESES = set(range(1, 13))

model = DelayModel()


class Flight(BaseModel):
    OPERA: str
    TIPOVUELO: str
    MES: int

    @validator("OPERA")
    def validate_opera(cls, value: str) -> str:
        if value not in VALID_OPERAS:
            raise ValueError("Invalid OPERA")
        return value

    @validator("TIPOVUELO")
    def validate_tipo_vuelo(cls, value: str) -> str:
        if value not in VALID_TIPOS_VUELO:
            raise ValueError("Invalid TIPOVUELO")
        return value

    @validator("MES")
    def validate_mes(cls, value: int) -> int:
        if value not in VALID_MESES:
            raise ValueError("Invalid MES")
        return value


class PredictRequest(BaseModel):
    flights: List[Flight]


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: fastapi.Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid request"},
    )


def get_model() -> DelayModel:
    if model._model is None:
        if MODEL_PATH.exists():
            model.load()
        else:
            logger.warning("Model artifact not found at %s, training from data.csv", MODEL_PATH)
            model._fit_from_default_data()
            model.save()
    return model


def flight_to_dict(flight: Flight) -> dict:
    if hasattr(flight, "model_dump"):
        return flight.model_dump()
    return flight.dict()

@app.get("/health", status_code=200)
async def get_health() -> dict:
    return {
        "status": "OK"
    }

@app.post("/predict", status_code=200)
async def post_predict(request: PredictRequest) -> dict:
    data = pd.DataFrame([flight_to_dict(flight) for flight in request.flights])
    fitted_model = get_model()
    features = fitted_model.preprocess(data=data)
    predictions = fitted_model.predict(features=features)
    return {"predict": predictions}

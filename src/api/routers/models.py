from fastapi import APIRouter
from src.api.services.data_loader import data_loader
from src.api.schemas.responses import ModelsStatusResponse

router = APIRouter()


@router.get("/models/status", response_model=ModelsStatusResponse)
def get_models_status():
    """
    Get the health and metadata of all trained ML models.

    Returns availability, file size, last modification time,
    and latest evaluation metrics for each registered model
    (LSTM Autoencoder, Isolation Forest, XGBoost, Bi-LSTM).
    """
    return data_loader.get_model_status()

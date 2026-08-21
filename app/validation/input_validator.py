import os
from app.config import config
from app.errors.exceptions import ValidationError
from app.logger import get_logger

logger = get_logger(__name__)


def validate_file(file_name: str, file_size_bytes: int) -> None:
    if not file_name or "." not in file_name:
        raise ValidationError("File has no extension.")

    ext = file_name.rsplit(".", 1)[-1].lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '.{ext}'. Allowed: {sorted(config.ALLOWED_EXTENSIONS)}"
        )

    if file_size_bytes <= 0:
        raise ValidationError("Uploaded file is empty.")

    max_bytes = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise ValidationError(
            f"File exceeds max upload size of {config.MAX_UPLOAD_SIZE_MB}MB."
        )

    logger.info("File '%s' passed validation (%d bytes)", file_name, file_size_bytes)
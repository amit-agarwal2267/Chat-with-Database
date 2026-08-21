import pandas as pd
from app.validation.input_validator import validate_file
from app.errors.exceptions import DataLoadError
from app.logger import get_logger

logger = get_logger(__name__)


def load_dataframe(file_path: str, file_name: str, file_size_bytes: int) -> pd.DataFrame:
    validate_file(file_name, file_size_bytes)
    ext = file_name.rsplit(".", 1)[-1].lower()

    try:
        if ext == "csv":
            df = pd.read_csv(file_path)
        elif ext in ("xlsx", "xls"):
            df = pd.read_excel(file_path)
        else:
            raise DataLoadError(f"No loader implemented for extension '.{ext}'")
    except (pd.errors.ParserError, ValueError) as e:
        raise DataLoadError(f"Failed to parse '{file_name}': {e}") from e

    if df.empty:
        raise DataLoadError(f"'{file_name}' loaded but contains no rows.")

    logger.info("Loaded '%s' with shape %s", file_name, df.shape)
    return df
import pandas as pd
from app.errors.exceptions import SchemaExtractionError
from app.logger import get_logger

logger = get_logger(__name__)


def extract_schema(df: pd.DataFrame) -> dict:
    try:
        columns = []
        for col in df.columns:
            series = df[col]
            columns.append({
                "name": col,
                "dtype": str(series.dtype),
                "null_count": int(series.isna().sum()),
                "unique_count": int(series.nunique()),
                "sample_values": series.dropna().unique()[:5].tolist(),
            })

        schema = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": columns,
        }
        logger.info("Extracted schema: %d rows, %d columns", schema["row_count"], schema["column_count"])
        return schema
    except Exception as e:
        raise SchemaExtractionError(f"Schema extraction failed: {e}") from e
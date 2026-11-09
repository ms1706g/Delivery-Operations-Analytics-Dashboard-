
"""
Silver Layer - Data Transformation

Responsibilities:
- Read the latest complete Bronze batch.
- Validate source schemas.
- Remove exact duplicate records.
- Convert source data types.
- Preserve optional missing values.
- Quarantine invalid records with rejection reasons.
- Write clean Parquet datasets and quality reports.
"""

import json
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"
SILVER_DIR = PROJECT_ROOT / "data" / "silver"
QUARANTINE_DIR = SILVER_DIR / "quarantine"


# --------------------------------------------------
# EXPECTED SCHEMAS
# --------------------------------------------------

EXPECTED_COLUMNS = {
    "orders": [
        "order_id",
        "order_date",
        "rider_id",
        "city",
        "delivery_distance_km",
        "delivery_time_minutes",
        "customer_rating",
        "order_value",
        "delivery_status",
    ],

    "riders": [
        "rider_id",
        "rider_name",
        "joining_date",
        "city",
        "vehicle_type",
        "employment_type",
        "shift_hours",
    ],

    "payout_ratecard": [
        "vehicle_type",
        "base_payout",
        "payout_per_km",
        "payout_per_order",
    ],

    "third_party_feed": [
        "order_id",
        "distance",
        "partner_fee",
        "delivery_time",
    ],
}


EXPECTED_COUNTS = {
    "orders": 60075,
    "riders": 600,
    "payout_ratecard": 3,
    "third_party_feed": 12000,
}


# --------------------------------------------------
# DATA TYPES
# --------------------------------------------------

NUMERIC_COLUMNS = {
    "orders": [
        "delivery_distance_km",
        "delivery_time_minutes",
        "customer_rating",
        "order_value",
    ],

    "riders": [
        "shift_hours",
    ],

    "payout_ratecard": [
        "base_payout",
        "payout_per_km",
        "payout_per_order",
    ],

    "third_party_feed": [
        "distance",
        "partner_fee",
        "delivery_time",
    ],
}


DATE_COLUMNS = {
    "orders": [
        "order_date",
    ],

    "riders": [
        "joining_date",
    ],
}


# --------------------------------------------------
# LOAD BRONZE RECORDS
# --------------------------------------------------

def load_batch_records(
    batch_file: Path,
) -> List[Dict[str, Any]]:

    """Load records from a Bronze JSONL batch."""

    records = []

    with batch_file.open(
        "r",
        encoding="utf-8"
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1
        ):

            if not line.strip():
                continue

            envelope = json.loads(line)

            required = {
                "source_file",
                "source_checksum",
                "ingestion_timestamp",
                "batch_id",
                "record",
            }

            if not required.issubset(envelope):
                raise ValueError(
                    f"Missing metadata at line {line_number}"
                )

            if not isinstance(
                envelope["record"],
                dict
            ):
                raise ValueError(
                    f"Invalid record at line {line_number}"
                )

            records.append(envelope["record"])

    return records


# --------------------------------------------------
# FIND LATEST COMPLETE BATCH
# --------------------------------------------------

def get_latest_complete_batch(
    source_name: str,
) -> Path:

    """Find latest batch matching expected source count."""

    source_dir = BRONZE_DIR / source_name

    if not source_dir.exists():
        raise FileNotFoundError(source_dir)

    expected_count = EXPECTED_COUNTS[source_name]

    batches = sorted(
        source_dir.glob("batch_*.jsonl"),
        reverse=True,
    )

    for batch_file in batches:

        records = load_batch_records(batch_file)

        if len(records) == expected_count:
            return batch_file

    raise ValueError(
        f"No complete Bronze batch found for {source_name}"
    )


# --------------------------------------------------
# SCHEMA VALIDATION
# --------------------------------------------------

def validate_schema(
    dataframe: pd.DataFrame,
    source_name: str,
) -> None:

    """Validate required source columns."""

    expected = set(
        EXPECTED_COLUMNS[source_name]
    )

    actual = set(dataframe.columns)

    missing = expected - actual
    unexpected = actual - expected

    if missing or unexpected:

        raise ValueError(
            f"{source_name} schema mismatch. "
            f"Missing: {missing}; "
            f"Unexpected: {unexpected}"
        )


# --------------------------------------------------
# PARQUET WRITER
# --------------------------------------------------

def write_parquet(
    dataframe: pd.DataFrame,
    output_path: Path,
) -> None:

    """Write a consistently typed DataFrame to Parquet."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Validate object columns before writing.
    for column in dataframe.select_dtypes(
        include=["object"]
    ).columns:

        types = (
            dataframe[column]
            .dropna()
            .map(lambda value: type(value).__name__)
            .unique()
        )

        if len(types) > 1:

            raise TypeError(
                f"Mixed data types in column "
                f"'{column}': {types}"
            )

    dataframe.to_parquet(
        output_path,
        engine="pyarrow",
        index=False,
    )


# --------------------------------------------------
# TRANSFORM DATASET
# --------------------------------------------------

def transform_dataset(
    source_name: str,
) -> Dict[str, Any]:

    """Transform one Bronze dataset into Silver."""

    print(f"\nProcessing dataset: {source_name}")

    # Load latest complete batch.
    batch_file = get_latest_complete_batch(
        source_name
    )

    records = load_batch_records(batch_file)

    dataframe = pd.DataFrame(records)

    # Validate source schema.
    validate_schema(
        dataframe,
        source_name,
    )

    dataframe = dataframe[
        EXPECTED_COLUMNS[source_name]
    ].copy()

    input_count = len(dataframe)

    # --------------------------------------------------
    # NORMALIZE WHITESPACE
    # --------------------------------------------------

    dataframe = dataframe.replace(
        r"^\s*$",
        pd.NA,
        regex=True,
    )

    # --------------------------------------------------
    # REMOVE EXACT DUPLICATES
    # --------------------------------------------------

    duplicate_mask = dataframe.duplicated(
        keep="first"
    )

    duplicate_records = dataframe.loc[
        duplicate_mask
    ].copy()

    duplicate_records[
        "_quarantine_reason"
    ] = "exact_duplicate"

    clean = dataframe.loc[
        ~duplicate_mask
    ].copy()

    # --------------------------------------------------
    # DATE CONVERSION
    # --------------------------------------------------

    invalid_date_mask = pd.Series(
        False,
        index=clean.index,
    )

    for column in DATE_COLUMNS.get(
        source_name,
        []
    ):

        parsed_dates = pd.to_datetime(
            clean[column],
            errors="coerce",
        )

        invalid_values = (
            clean[column].notna()
            & parsed_dates.isna()
        )

        invalid_date_mask |= invalid_values

        clean[column] = parsed_dates

    # --------------------------------------------------
    # NUMERIC CONVERSION
    # --------------------------------------------------

    invalid_numeric_mask = pd.Series(
        False,
        index=clean.index,
    )

    for column in NUMERIC_COLUMNS[source_name]:

        original = clean[column]

        converted = pd.to_numeric(
            original,
            errors="coerce",
        )

        invalid_values = (
            original.notna()
            & converted.isna()
        )

        invalid_numeric_mask |= invalid_values

        # Force consistent numeric dtype.
        clean[column] = converted.astype(
            "float64"
        )

    # --------------------------------------------------
    # CUSTOMER RATING VALIDATION
    # --------------------------------------------------

    if source_name == "orders":

        rating = clean["customer_rating"]

        invalid_rating_range = (
            rating.notna()
            & ~rating.between(1, 5)
        )

        invalid_numeric_mask |= (
            invalid_rating_range
        )

    # --------------------------------------------------
    # STRING TYPE NORMALIZATION
    # --------------------------------------------------

    string_columns = [
        column
        for column in EXPECTED_COLUMNS[source_name]
        if (
            column not in NUMERIC_COLUMNS[source_name]
            and column not in DATE_COLUMNS.get(
                source_name,
                []
            )
        )
    ]

    for column in string_columns:

        clean[column] = clean[column].astype(
            "string"
        )

    # --------------------------------------------------
    # REQUIRED FIELD VALIDATION
    # --------------------------------------------------

    required_columns = [
        column
        for column in EXPECTED_COLUMNS[source_name]
        if not (
            source_name == "orders"
            and column == "customer_rating"
        )
    ]

    missing_required_mask = dataframe.loc[
        clean.index, required_columns
    ].isna().any(axis=1)

    # --------------------------------------------------
    # REJECTION CONDITIONS
    # --------------------------------------------------

    rejection_mask = (
        invalid_date_mask
        | invalid_numeric_mask
        | missing_required_mask
    )

    rejected_records = clean.loc[
        rejection_mask
    ].copy()

    # --------------------------------------------------
    # QUARANTINE REASONS
    # --------------------------------------------------

    reasons = []

    for index in rejected_records.index:

        row_reasons = []

        if invalid_date_mask.loc[index]:
            row_reasons.append("invalid_date")

        if invalid_numeric_mask.loc[index]:
            row_reasons.append(
                "invalid_numeric_or_business_rule"
            )

        if missing_required_mask.loc[index]:
            row_reasons.append(
                "missing_required_field"
            )

        reasons.append(
            ";".join(row_reasons)
        )

    rejected_records[
        "_quarantine_reason"
    ] = reasons

    # --------------------------------------------------
    # VALID RECORDS
    # --------------------------------------------------

    valid_records = clean.loc[
        ~rejection_mask
    ].copy()

    # --------------------------------------------------
    # COMBINE QUARANTINE RECORDS
    # --------------------------------------------------

    quarantine_records = pd.concat(
        [
            duplicate_records,
            rejected_records,
        ],
        ignore_index=True,
    )


    for column in EXPECTED_COLUMNS[source_name]:
        quarantine_records[column] = (
        quarantine_records[column].astype("string")
    )

    quarantine_records["_quarantine_reason"] = (
        quarantine_records["_quarantine_reason"].astype("string")
    )


    # --------------------------------------------------
    # WRITE SILVER DATASET
    # --------------------------------------------------

    output_file = (
        SILVER_DIR
        / source_name
        / f"{source_name}.parquet"
    )

    write_parquet(
        valid_records,
        output_file,
    )

    # --------------------------------------------------
    # WRITE QUARANTINE DATASET
    # --------------------------------------------------

    quarantine_file = (
        QUARANTINE_DIR
        / f"{source_name}_rejected.parquet"
    )

    if not quarantine_records.empty:

        write_parquet(
            quarantine_records,
            quarantine_file,
        )

    # --------------------------------------------------
    # QUALITY REPORT
    # --------------------------------------------------

    report = {

        "dataset": source_name,

        "source_batch": batch_file.name,

        "input_records": input_count,

        "exact_duplicates": len(
            duplicate_records
        ),

        "invalid_records": len(
            rejected_records
        ),

        "quarantined_records": len(
            quarantine_records
        ),

        "output_records": len(
            valid_records
        ),

        "optional_null_ratings": (
            int(
                valid_records[
                    "customer_rating"
                ].isna().sum()
            )
            if source_name == "orders"
            else None
        ),

        "output_path": str(output_file),

        "quarantine_path": str(
            quarantine_file
        ),
    }

    print(
        json.dumps(
            report,
            indent=2,
        )
    )

    return report


# --------------------------------------------------
# RUN SILVER PIPELINE
# --------------------------------------------------

def run_silver_pipeline() -> None:

    """Run Silver transformations for all datasets."""

    reports = []

    for source_name in EXPECTED_COLUMNS:

        report = transform_dataset(
            source_name
        )

        reports.append(report)

    # --------------------------------------------------
    # WRITE QUALITY REPORT
    # --------------------------------------------------

    report_file = (
        SILVER_DIR
        / "quality_report.json"
    )

    report_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with report_file.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            reports,
            file,
            indent=2,
        )

    print("\nSilver pipeline completed successfully.")

    print(
        f"Quality report: {report_file}"
    )


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":

    run_silver_pipeline()

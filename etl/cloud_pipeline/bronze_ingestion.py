
"""
Bronze Layer - Source Data Ingestion

Responsibilities:
- Read CSV and JSON source files.
- Preserve original source records.
- Attach ingestion metadata.
- Write immutable JSONL snapshots.
"""

import csv
import json
import hashlib

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Dict, Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SOURCE_DIR = PROJECT_ROOT / "data"
BRONZE_DIR = SOURCE_DIR / "bronze"


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of the source file."""

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def read_csv_records(
    file_path: Path
) -> Iterator[Dict[str, Any]]:
    """Read CSV records without modifying source values."""

    with file_path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("CSV file has no header.")

        for row in reader:
            yield dict(row)


def read_json_records(
    file_path: Path
) -> Iterator[Dict[str, Any]]:
    """Read JSON records from supported JSON structures."""

    with file_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        payload = json.load(file)

    # Format 1: Root-level JSON list
    if isinstance(payload, list):
        records = payload

    # Format 2: Wrapped JSON object
    elif isinstance(payload, dict):

        if "partner_orders" in payload:
            records = payload["partner_orders"]

        else:
            list_values = [
                value
                for value in payload.values()
                if isinstance(value, list)
            ]

            if len(list_values) != 1:
                raise ValueError(
                    "JSON structure is ambiguous. "
                    "Specify the records key explicitly."
                )

            records = list_values[0]

    else:
        raise ValueError(
            "Unsupported JSON root structure."
        )

    if not isinstance(records, list):
        raise ValueError(
            "Expected a list of JSON records."
        )

    for index, record in enumerate(records):

        if not isinstance(record, dict):
            raise ValueError(
                f"Invalid record at index {index}: "
                "expected a JSON object."
            )

        yield record


def ingest_file(
    file_path: Path
) -> Dict[str, Any]:
    """Ingest one source file into a Bronze JSONL snapshot."""

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    extension = file_path.suffix.lower()

    if extension == ".csv":
        records = read_csv_records(file_path)

    elif extension == ".json":
        records = read_json_records(file_path)

    else:
        raise ValueError(
            "Only CSV and JSON files are supported."
        )

    # Calculate checksum only once per source file.
    source_checksum = calculate_checksum(file_path)

    # Generate batch metadata.
    timestamp = datetime.now(timezone.utc)

    batch_id = timestamp.strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    output_dir = BRONZE_DIR / file_path.stem

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        output_dir / f"batch_{batch_id}.jsonl"
    )

    count = 0

    # Exclusive creation prevents accidental overwriting.
    with output_file.open(
        "x",
        encoding="utf-8"
    ) as output:

        for record in records:

            envelope = {
                "source_file": file_path.name,
                "source_checksum": source_checksum,
                "ingestion_timestamp": timestamp.isoformat(),
                "batch_id": batch_id,
                "record": record
            }

            output.write(
                json.dumps(
                    envelope,
                    ensure_ascii=False
                ) + "\n"
            )

            count += 1

    return {
        "source": file_path.name,
        "records_ingested": count,
        "batch_id": batch_id,
        "source_checksum": source_checksum,
        "output_path": str(output_file)
    }


def run_bronze_ingestion() -> None:
    """Ingest all supported delivery source files."""

    source_files = [
        SOURCE_DIR / "orders.csv",
        SOURCE_DIR / "riders.csv",
        SOURCE_DIR / "payout_ratecard.csv",
        SOURCE_DIR / "third_party_feed.json"
    ]

    for source_file in source_files:

        result = ingest_file(source_file)

        print(
            json.dumps(
                result,
                indent=2
            )
        )


if __name__ == "__main__":
    run_bronze_ingestion()
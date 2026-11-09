from pathlib import Path

from aws.s3_uploader import upload_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"

BATCHES = [
    (
        "orders",
        "batch_20261109T140054420325Z.jsonl",
    ),
    (
        "riders",
        "batch_20261109T140357164109Z.jsonl",
    ),
    (
        "payout_ratecard",
        "batch_20261109T140357503710Z.jsonl",
    ),
    (
        "third_party_feed",
        "batch_20261109T140357513269Z.jsonl",
    ),
]


def main():
    successful_uploads = 0

    for source, filename in BATCHES:
        local_path = BRONZE_DIR / source / filename
        s3_key = f"bronze/{source}/{filename}"

        print(f"\nUploading: {source}")

        if not local_path.is_file():
            raise FileNotFoundError(local_path)

        success = upload_file(
            local_file_path=str(local_path),
            s3_key=s3_key,
        )

        if not success:
            raise RuntimeError(
                f"Upload failed for {source}. Stopping pipeline."
            )

        successful_uploads += 1

    print(
        f"\nBronze upload completed: "
        f"{successful_uploads}/{len(BATCHES)} files."
    )


if __name__ == "__main__":
    main()
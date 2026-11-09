from pathlib import Path

from aws.s3_uploader import upload_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SILVER_DIR = PROJECT_ROOT / "data" / "silver"

FILES = [
    "orders/orders.parquet",
    "riders/riders.parquet",
    "payout_ratecard/payout_ratecard.parquet",
    "third_party_feed/third_party_feed.parquet",
    "quarantine/orders_rejected.parquet",
    "quality_report.json",
]


def main():
    successful_uploads = 0

    for relative_path in FILES:
        local_path = SILVER_DIR / relative_path
        s3_key = f"silver/{relative_path}"

        print(f"\nUploading: {relative_path}")

        if not local_path.is_file():
            raise FileNotFoundError(local_path)

        success = upload_file(
            local_file_path=str(local_path),
            s3_key=s3_key,
        )

        if not success:
            raise RuntimeError(
                f"Upload failed for {relative_path}. "
                "Stopping pipeline."
            )

        successful_uploads += 1

    print(
        f"\nSilver upload completed: "
        f"{successful_uploads}/{len(FILES)} files."
    )


if __name__ == "__main__":
    main()
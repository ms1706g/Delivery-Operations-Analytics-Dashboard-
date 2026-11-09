from pathlib import Path

from aws.s3_uploader import upload_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = PROJECT_ROOT / "data" / "gold"

FILES = [
    "delivery_performance_by_city.parquet",
    "rider_performance_and_payout.parquet",
]


def main():
    successful_uploads = 0

    for filename in FILES:
        local_path = GOLD_DIR / filename
        s3_key = f"gold/{filename}"

        print(f"\nUploading: {filename}")

        if not local_path.is_file():
            raise FileNotFoundError(local_path)

        success = upload_file(
            local_file_path=str(local_path),
            s3_key=s3_key,
        )

        if not success:
            raise RuntimeError(
                f"Upload failed for {filename}. Stopping pipeline."
            )

        successful_uploads += 1

    print(
        f"\nGold upload completed: "
        f"{successful_uploads}/{len(FILES)} files."
    )


if __name__ == "__main__":
    main()
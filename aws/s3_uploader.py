
from pathlib import Path

from botocore.exceptions import ClientError

from aws.s3_client import get_s3_client, BUCKET_NAME


def upload_file(
    local_file_path: str,
    s3_key: str,
) -> bool:
    """
    Upload a local file to the configured S3 bucket.

    Args:
        local_file_path: Path of the local file.
        s3_key: Destination object key in S3.

    Returns:
        True if upload succeeds, otherwise False.
    """

    file_path = Path(local_file_path)

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    if not file_path.is_file():
        raise ValueError("Source path must be a file.")

    s3_client = get_s3_client()

    try:
        s3_client.upload_file(
            str(file_path),
            BUCKET_NAME,
            s3_key,
        )

        print("Upload successful!")
        print("File:", file_path.name)
        print("S3 location:", f"s3://{BUCKET_NAME}/{s3_key}")

        return True

    except ClientError as error:
        print("Upload failed:")
        print(error.response["Error"]["Code"])
        return False


if __name__ == "__main__":
    print("S3 uploader module ready.")

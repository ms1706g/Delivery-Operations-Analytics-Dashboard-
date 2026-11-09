
from pathlib import Path

from aws.s3_uploader import upload_file


def main():
    test_file = Path("s3_test.txt")

    if not test_file.exists():
        test_file.write_text(
            "Testing Python Boto3 upload to Amazon S3.",
            encoding="utf-8",
        )

    upload_file(
        local_file_path=str(test_file),
        s3_key="test/boto3_upload_test.txt",
    )


if __name__ == "__main__":
    main()

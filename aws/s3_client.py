
import boto3
from botocore.exceptions import ClientError


AWS_REGION = "ap-south-1"
BUCKET_NAME = "manan-delivery-ops-analytics-2026"


def get_s3_client():
    """Create an S3 client using AWS CLI credentials."""

    return boto3.client(
        "s3",
        region_name=AWS_REGION,
    )


def verify_bucket_access():
    """Verify access to the project S3 bucket."""

    s3_client = get_s3_client()

    try:
        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            MaxKeys=5,
        )

        print("S3 connection successful!")
        print("Bucket:", BUCKET_NAME)
        print("Objects found:", response.get("KeyCount", 0))

        return True

    except ClientError as error:
        print("S3 connection failed:")
        print(error.response["Error"]["Code"])
        return False


if __name__ == "__main__":
    verify_bucket_access()

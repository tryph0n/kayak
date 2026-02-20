"""S3 storage operations."""

import io

import boto3
import pandas as pd
from botocore.exceptions import ClientError


class S3Storage:
    """Client for AWS S3 storage operations.

    Attributes:
        bucket_name: S3 bucket name.
        region: AWS region.
        s3: Boto3 S3 resource.
        bucket: S3 bucket resource.
    """

    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region: str = "eu-west-3",
    ):
        """Initialize S3 storage client.

        Args:
            bucket_name: S3 bucket name.
            aws_access_key_id: AWS access key.
            aws_secret_access_key: AWS secret key.
            region: AWS region (default: eu-west-3).
        """
        self.bucket_name = bucket_name
        self.region = region
        self.s3 = boto3.resource(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region,
        )
        self.bucket = self.s3.Bucket(bucket_name)

    def file_exists(self, key: str) -> bool:
        """Check if a specific file exists in S3.

        Args:
            key: S3 object key (e.g., "kayak/processed/weather_scored.csv").

        Returns:
            bool: True if file exists, False otherwise.
        """
        try:
            self.s3.Object(self.bucket_name, key).load()
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            raise

    def upload_dataframe(self, df: pd.DataFrame, key: str):
        """Upload a pandas DataFrame as CSV to S3.

        Args:
            df: DataFrame to upload.
            key: S3 object key (file path in bucket).

        Raises:
            Exception: If upload fails.
        """
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)

        try:
            self.bucket.put_object(
                Key=key,
                Body=csv_buffer.getvalue(),
                ContentType="text/csv",
            )
        except Exception as e:
            raise Exception(f"Failed to upload to S3: {str(e)}") from e

    def download_dataframe(self, key: str):
        """Download a CSV file from S3 as a DataFrame.

        Args:
            key: S3 object key.

        Returns:
            pd.DataFrame: Downloaded data.

        Raises:
            Exception: If download fails.
        """
        try:
            obj = self.bucket.Object(key)
            return pd.read_csv(io.BytesIO(obj.get()['Body'].read()))
        except Exception as e:
            raise Exception(f"Failed to download from S3: {str(e)}") from e

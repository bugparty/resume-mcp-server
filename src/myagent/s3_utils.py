from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


def _get_s3_client_and_settings() -> tuple[Any, str, str, str]:
    """Create an S3 client using resume-related environment variables."""
    s3_bucket = (
        os.getenv("RESUME_S3_BUCKET_NAME")
        or os.getenv("RESUME_S3_BUCKET")
        or os.getenv("S3_BUCKET_NAME")
    )
    if not s3_bucket:
        raise RuntimeError(
            "Resume S3 bucket not configured. Set RESUME_S3_BUCKET_NAME or S3_BUCKET_NAME."
        )

    s3_endpoint = os.getenv("RESUME_S3_ENDPOINT_URL") or os.getenv("S3_ENDPOINT_URL")
    s3_region = os.getenv("RESUME_S3_REGION") or os.getenv("AWS_REGION")
    access_key = (
        os.getenv("RESUME_S3_ACCESS_KEY_ID")
        or os.getenv("RESUME_S3_ACCESS_KEY")
        or os.getenv("S3_ACCESS_KEY_ID")
        or os.getenv("AWS_ACCESS_KEY_ID")
    )
    secret_key = (
        os.getenv("RESUME_S3_SECRET_ACCESS_KEY")
        or os.getenv("RESUME_S3_SECRET_KEY")
        or os.getenv("S3_SECRET_ACCESS_KEY")
        or os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    client_kwargs: dict[str, Any] = {}
    if s3_endpoint:
        client_kwargs["endpoint_url"] = s3_endpoint
    if s3_region:
        client_kwargs["region_name"] = s3_region
    if access_key and secret_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key

    s3_config_kwargs: dict[str, Any] = {"signature_version": "s3v4"}
    addressing_style = os.getenv("RESUME_S3_ADDRESSING_STYLE")
    if not addressing_style and s3_endpoint:
        endpoint_host = urlparse(s3_endpoint).hostname or ""
        if endpoint_host and not endpoint_host.endswith("amazonaws.com"):
            addressing_style = "path"
    if addressing_style:
        s3_config_kwargs["s3"] = {"addressing_style": addressing_style}
    client_kwargs["config"] = Config(**s3_config_kwargs)

    try:
        s3_client = boto3.client("s3", **client_kwargs)
    except Exception as exc:  # pragma: no cover - boto3 can raise various subclasses
        logger.error("Failed to create S3 client: %s", exc, exc_info=True)
        raise RuntimeError("Failed to create S3 client for resume uploads") from exc

    key_prefix = os.getenv("RESUME_S3_KEY_PREFIX", "resumes/")
    if key_prefix and not key_prefix.endswith("/"):
        key_prefix = f"{key_prefix}/"

    public_base_url = os.getenv("RESUME_S3_PUBLIC_BASE_URL")
    if not public_base_url:
        raise RuntimeError(
            "RESUME_S3_PUBLIC_BASE_URL must be set to the public R2 domain "
            "(e.g., https://pub-xxxxx.r2.dev or your custom domain)"
        )
    if not public_base_url.endswith("/"):
        public_base_url += "/"

    return s3_client, s3_bucket, key_prefix, public_base_url


def _build_object_key(filename: str, key_prefix: str) -> str:
    return f"{key_prefix}{filename}" if key_prefix else filename


def _ensure_s3_object_available(
    s3_client: Any, bucket: str, object_key: str, description: str
) -> None:
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            s3_client.head_object(Bucket=bucket, Key=object_key)
            return
        except (BotoCoreError, ClientError) as exc:
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey"} and attempt < max_attempts:
                time.sleep(0.4 * attempt)
                continue
            logger.error(
                "Failed to verify availability for '%s' in bucket '%s' after attempt %d/%d: %s",
                object_key,
                bucket,
                attempt,
                max_attempts,
                exc,
                exc_info=True,
            )
            raise RuntimeError(
                f"Uploaded {description} is not yet available for download"
            ) from exc


def upload_bytes_to_s3(
    data: bytes, filename: str, content_type: str, description: str
) -> tuple[str, str]:
    s3_client, s3_bucket, key_prefix, public_base_url = _get_s3_client_and_settings()
    object_key = _build_object_key(filename, key_prefix)

    try:
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error(
            "Failed to upload %s '%s' to bucket '%s': %s",
            description,
            filename,
            s3_bucket,
            exc,
            exc_info=True,
        )
        raise RuntimeError(f"Failed to upload {description} to S3") from exc

    _ensure_s3_object_available(s3_client, s3_bucket, object_key, description)

    public_url = f"{public_base_url}{object_key}"
    return public_url, object_key


def download_s3_object_bytes(object_key: str, description: str) -> bytes:
    s3_client, s3_bucket, _, _ = _get_s3_client_and_settings()
    try:
        response = s3_client.get_object(Bucket=s3_bucket, Key=object_key)
        return response["Body"].read()
    except (BotoCoreError, ClientError) as exc:
        logger.error(
            "Failed to download %s '%s' from bucket '%s': %s",
            description,
            object_key,
            s3_bucket,
            exc,
            exc_info=True,
        )
        raise RuntimeError(f"Failed to download {description} from S3") from exc


def download_s3_object_to_file(
    object_key: str, destination: Path, description: str
) -> None:
    data = download_s3_object_bytes(object_key, description)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


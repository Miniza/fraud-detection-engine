import boto3
from .config import settings


def get_boto_client(service_name: str):
    """
    Returns a configured boto3 client.
    In local dev, it points to the Moto endpoint.
    """
    return boto3.client(
        service_name,
        region_name=settings.AWS_REGION,
        endpoint_url=settings.AWS_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

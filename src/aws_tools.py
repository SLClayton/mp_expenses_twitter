import json
from typing import Dict, Any, Union

import boto3

from tools import *

TABLE_NAME = os.getenv("MPE_DDB_TABLE_NAME")
S3_CLIENT = boto3.client("s3")
SECRETS_MANAGER = boto3.client("secretsmanager")
DYNAMODB = boto3.resource("dynamodb")
DDB_TABLE = DYNAMODB.Table(TABLE_NAME)


def in_aws() -> bool:
    return os.environ.get("AWS_EXECUTION_ENV") is not None


def get_secret_dict(name: str) -> Dict[str, Any]:
    return json.loads(get_secret_string(name))


def get_secret_string(name: str) -> str:
    print(f"Requesting secret from AWS secret manager: {name}")
    secret_str = SECRETS_MANAGER.get_secret_value(SecretId=name)["SecretString"]
    print(f"Secret found.")
    return secret_str


def save_item_to_db(item: dict) -> None:
    DDB_TABLE.put_item(Item=item)


def item_in_db(item_id: Union[str, int]) -> bool:
    try:
        response = DDB_TABLE.get_item(Key={"expense_id": str(item_id)})
        return "Item" in response
    except Exception as e:
        print("Error checking item:", e)

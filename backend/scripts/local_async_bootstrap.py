# ruff: noqa: T20 - prints progress for the developer watching `make start-backend-docker`
"""Build the local async stack from `template.yaml`, and seed a corpus the planner can plan from.

`make start-backend-docker` runs this before the API and the worker: DynamoDB Local gets every table
the template declares (with the TTL attribute where one is declared), ElasticMQ gets the session
queue and its dead-letter queue with the template's redrive policy, and the filesystem recipe corpus
gets four sample dinners if it is empty, so a session can actually complete without the prod corpus.

Idempotent, so it can run on every `up`.
"""

from __future__ import annotations

import json
import os
from typing import Any, NamedTuple

import boto3
import yaml
from botocore.exceptions import ClientError

TEMPLATE = os.environ.get("GLEAN_TEMPLATE", "/app/template.yaml")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
REGION = os.environ.get("AWS_REGION", "eu-west-2")
ACCOUNT = "000000000000"
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://dynamodb-local:8000")
SQS_ENDPOINT = os.environ.get("SQS_ENDPOINT_URL", "http://elasticmq:9324")

# CloudFormation-only properties that create_table does not take, and the TTL one it takes separately.
_CFN_ONLY = {"TableName", "TableClass", "PointInTimeRecoverySpecification", "TimeToLiveSpecification", "Tags"}

_SAMPLE_RECIPES = {
    "rec_local_coriander_chicken": ("Coriander Chicken", ["chicken breast", "coriander", "rice"]),
    "rec_local_lentil_bake": ("Lentil Bake", ["lentils", "potato", "tomato"]),
    "rec_local_tofu_noodles": ("Tofu Noodles", ["tofu", "noodles", "soy sauce"]),
    "rec_local_chickpea_curry": ("Chickpea Curry", ["chickpeas", "coconut milk", "rice"]),
}


class _CfnLoader(yaml.SafeLoader):
    """Reads CloudFormation short-form tags as `{tag: value}`, so intrinsics can be resolved here."""


def _intrinsic(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> dict[str, Any]:
    if isinstance(node, yaml.ScalarNode):
        value: Any = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {suffix: value}


_CfnLoader.add_multi_constructor("!", _intrinsic)


def main() -> int:
    with open(TEMPLATE, encoding="utf-8") as handle:
        template = yaml.load(handle, Loader=_CfnLoader)  # noqa: S506 - subclass of SafeLoader
    dynamodb = boto3.client("dynamodb", region_name=REGION, endpoint_url=DYNAMODB_ENDPOINT)
    sqs = boto3.client("sqs", region_name=REGION, endpoint_url=SQS_ENDPOINT)

    resources = template["Resources"]
    for resource in resources.values():
        if resource["Type"] == "AWS::DynamoDB::Table":
            _create_table(dynamodb, resource["Properties"])

    # Dead letter queues first: the queue that names one needs its ARN.
    queues = {
        name: _ensure_queue(sqs, resource["Properties"])
        for name, resource in resources.items()
        if resource["Type"] == "AWS::SQS::Queue" and "RedrivePolicy" not in resource["Properties"]
    }
    queues |= {
        name: _ensure_queue(sqs, resource["Properties"])
        for name, resource in resources.items()
        if resource["Type"] == "AWS::SQS::Queue" and "RedrivePolicy" in resource["Properties"]
    }
    for name, resource in resources.items():
        if resource["Type"] == "AWS::SQS::Queue" and "RedrivePolicy" in resource["Properties"]:
            _apply_redrive(sqs, queues, name, resource["Properties"]["RedrivePolicy"])

    _seed_corpus()
    print("local async stack ready")
    return 0


def _name(value: Any) -> str:
    """Resolve a `!Sub` queue or table name for this environment."""
    raw = value["Sub"] if isinstance(value, dict) and "Sub" in value else str(value)
    return raw.replace("${Environment}", ENVIRONMENT).replace("${AWS::AccountId}", ACCOUNT)


def _create_table(dynamodb: Any, properties: dict[str, Any]) -> None:
    table_name = _name(properties["TableName"])
    parameters = {key: value for key, value in properties.items() if key not in _CFN_ONLY}
    parameters["TableName"] = table_name
    try:
        dynamodb.create_table(**parameters)
        print(f"created table {table_name}")
    except ClientError as error:
        if error.response["Error"]["Code"] != "ResourceInUseException":
            raise
        print(f"table {table_name} already exists")
    ttl = properties.get("TimeToLiveSpecification")
    if ttl:
        try:
            dynamodb.update_time_to_live(TableName=table_name, TimeToLiveSpecification=ttl)
        except ClientError:
            # DynamoDB Local ignores TTL; the template's specification is what production runs.
            print(f"table {table_name}: DynamoDB Local did not apply the TTL specification")


class Queue(NamedTuple):
    url: str
    arn: str


def _ensure_queue(sqs: Any, properties: dict[str, Any]) -> Queue:
    queue_name = _name(properties["QueueName"])
    attributes = {
        key: str(value)
        for key, value in properties.items()
        if key in {"VisibilityTimeout", "MessageRetentionPeriod", "ReceiveMessageWaitTimeSeconds"}
    }
    url = sqs.create_queue(QueueName=queue_name, Attributes=attributes)["QueueUrl"]
    arn = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    print(f"queue {queue_name} ready at {url}")
    return Queue(url=url, arn=arn)


def _apply_redrive(sqs: Any, queues: dict[str, Queue], name: str, policy: dict[str, Any]) -> None:
    """Wire the dead-letter target the template names, by logical id."""
    dead_letter = policy["deadLetterTargetArn"]
    target = dead_letter["GetAtt"].split(".")[0] if isinstance(dead_letter, dict) and "GetAtt" in dead_letter else None
    if target not in queues:
        raise SystemExit(f"{name}: cannot resolve the dead-letter queue {dead_letter!r}")
    sqs.set_queue_attributes(
        QueueUrl=queues[name].url,
        Attributes={
            "RedrivePolicy": json.dumps(
                {"deadLetterTargetArn": queues[target].arn, "maxReceiveCount": int(policy["maxReceiveCount"])}
            )
        },
    )
    print(f"queue {name}: messages past {policy['maxReceiveCount']} attempts go to {target}")


def _seed_corpus() -> None:
    """Four sample dinners in the local filesystem corpus, so a session has something to plan."""
    from glean.recipes.corpus import RecipeCorpusStore  # noqa: PLC0415 - only the local stack needs this
    from glean.recipes.stored import StoredIngredient, StoredRecipe  # noqa: PLC0415

    corpus = RecipeCorpusStore()
    if corpus.search(per_page=1)[0]:
        print("local corpus already has recipes")
        return
    for external_id, (title, ingredients) in _SAMPLE_RECIPES.items():
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
            )
        )
    print(f"seeded {len(_SAMPLE_RECIPES)} sample recipes into the local corpus")


if __name__ == "__main__":
    raise SystemExit(main())

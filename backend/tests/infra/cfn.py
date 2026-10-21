"""Load CloudFormation/SAM templates in tests, keeping intrinsic functions (!Sub, !Ref, ...) as plain values."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[2]
TEMPLATE = BACKEND_DIR / "template.yaml"
BOOTSTRAP = BACKEND_DIR.parent / "infra" / "bootstrap.yaml"


class _CfnLoader(yaml.SafeLoader):
    pass


def _intrinsic(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.ScalarNode):
        value: Any = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {tag_suffix: value}


_CfnLoader.add_multi_constructor("!", _intrinsic)


def load(path: Path) -> dict[str, Any]:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_CfnLoader)  # noqa: S506 - SafeLoader subclass


def catalogue_table_properties() -> dict[str, Any]:
    return load(TEMPLATE)["Resources"]["GleanCatalogueTable"]["Properties"]


def recipes_table_properties() -> dict[str, Any]:
    return load(TEMPLATE)["Resources"]["GleanRecipesTable"]["Properties"]


def dynamo_table_properties() -> dict[str, dict[str, Any]]:
    """Every DynamoDB table in the stack, by logical id, as the template declares it."""
    return {
        name: resource["Properties"]
        for name, resource in load(TEMPLATE)["Resources"].items()
        if resource["Type"] == "AWS::DynamoDB::Table"
    }


def sessions_table_properties() -> dict[str, Any]:
    return dynamo_table_properties()["GleanAgentSessionsTable"]


def checkpoints_table_properties() -> dict[str, Any]:
    return dynamo_table_properties()["GleanAgentCheckpointsTable"]


def queue_properties(logical_id: str) -> dict[str, Any]:
    return load(TEMPLATE)["Resources"][logical_id]["Properties"]


def functions() -> dict[str, dict[str, Any]]:
    """Every Lambda function in the stack, by logical id."""
    return {
        name: resource["Properties"]
        for name, resource in load(TEMPLATE)["Resources"].items()
        if resource["Type"] == "AWS::Serverless::Function"
    }

"""ADR 0001's budget alert and the deploy policies' reach, as declared in infra/bootstrap.yaml."""

from __future__ import annotations

import re
from typing import Any

import pytest

from tests.infra.cfn import BOOTSTRAP, load


@pytest.fixture(scope="module")
def resources() -> dict[str, Any]:
    return load(BOOTSTRAP)["Resources"]


def test_any_dynamodb_charge_raises_a_budget_alert(resources: dict[str, Any]) -> None:
    budgets = [r["Properties"] for r in resources.values() if r["Type"] == "AWS::Budgets::Budget"]
    assert len(budgets) == 1
    budget = budgets[0]["Budget"]
    assert budget["CostFilters"]["Service"] == ["Amazon DynamoDB"]
    notification = budgets[0]["NotificationsWithSubscribers"][0]["Notification"]
    assert notification["NotificationType"] == "ACTUAL"
    assert notification["ComparisonOperator"] == "GREATER_THAN"
    # Alerting at 100% of a one-cent limit means any charge at all.
    assert budget["BudgetLimit"] == {"Amount": 0.01, "Unit": "USD"}
    assert (notification["ThresholdType"], notification["Threshold"]) == ("PERCENTAGE", 100)


def test_the_alert_email_comes_from_a_stack_parameter_not_the_repo() -> None:
    template = load(BOOTSTRAP)
    subscriber = template["Resources"]["DynamoDbChargeBudget"]["Properties"]["NotificationsWithSubscribers"][0][
        "Subscribers"
    ][0]
    assert subscriber["Address"] == {"Ref": "AlertEmail"}
    assert "Default" not in template["Parameters"]["AlertEmail"]
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", BOOTSTRAP.read_text(encoding="utf-8"))


def test_the_deploy_policy_can_manage_only_the_prod_tables_and_queues(resources: dict[str, Any]) -> None:
    statements = resources["GleanDeployPolicyProd"]["Properties"]["PolicyDocument"]["Statement"]
    dynamo = [s for s in statements if "dynamodb:*" in _as_list(s["Action"])]
    assert len(dynamo) == 1
    assert [r["Sub"] for r in dynamo[0]["Resource"]] == [
        "arn:aws:dynamodb:*:${AWS::AccountId}:table/glean-catalogue-prod",
        "arn:aws:dynamodb:*:${AWS::AccountId}:table/glean-catalogue-prod/index/*",
        "arn:aws:dynamodb:*:${AWS::AccountId}:table/glean-agent-sessions-prod",
        "arn:aws:dynamodb:*:${AWS::AccountId}:table/glean-agent-checkpoints-prod",
    ]
    # CloudFormation creates the session queue and its dead-letter queue with the deploy role.
    sqs = [s for s in statements if "sqs:*" in _as_list(s["Action"])]
    assert len(sqs) == 1
    assert [r["Sub"] for r in sqs[0]["Resource"]] == [
        "arn:aws:sqs:*:${AWS::AccountId}:glean-agent-sessions-prod",
        "arn:aws:sqs:*:${AWS::AccountId}:glean-agent-sessions-dlq-prod",
    ]
    assert not any(a.startswith("budgets:") for s in statements for a in _as_list(s["Action"]))


def test_every_role_github_can_assume_is_pinned_to_an_approved_environment(resources: dict[str, Any]) -> None:
    """A role any workflow run could assume would bypass the prod environment's required reviewers."""
    github_roles = {
        name: r["Properties"]["AssumeRolePolicyDocument"]["Statement"]
        for name, r in resources.items()
        if r["Type"] == "AWS::IAM::Role"
        and any(
            s.get("Principal", {}).get("Federated") == {"GetAtt": "GitHubOidcProvider.Arn"}
            for s in r["Properties"]["AssumeRolePolicyDocument"]["Statement"]
        )
    }
    assert github_roles
    for name, statements in github_roles.items():
        for statement in statements:
            subjects = _as_list(statement["Condition"]["StringLike"]["token.actions.githubusercontent.com:sub"]["Sub"])
            assert subjects == ["repo:${GitHubOrg}/${GitHubRepo}:environment:prod"], name


def _as_list(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else value

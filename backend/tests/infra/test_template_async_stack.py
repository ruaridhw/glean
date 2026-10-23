"""The async stack as the template declares it: tables, queue, worker, and the free tier's budget."""

from __future__ import annotations

from typing import Any

from glean.sessions.store import LEASE_SECONDS, QUEUE_VISIBILITY_SECONDS, WORKER_TIMEOUT_SECONDS
from tests.infra.cfn import (
    TEMPLATE,
    checkpoints_table_properties,
    functions,
    load,
    queue_properties,
    sessions_table_properties,
)

# F1 (#162, open PR #194) adds the recipe store at 5/5; the free-tier sum in test_template_free_tier
# counts it, so this file only checks what each of the async stack's own tables declares.


def test_the_session_table_is_2_2_and_expires_its_items() -> None:
    props = sessions_table_properties()
    assert props["TableName"] == {"Sub": "glean-agent-sessions-${Environment}"}
    assert props["ProvisionedThroughput"] == {"ReadCapacityUnits": 2, "WriteCapacityUnits": 2}
    assert props["TimeToLiveSpecification"] == {"AttributeName": "ttl", "Enabled": True}
    assert [(key["AttributeName"], key["KeyType"]) for key in props["KeySchema"]] == [
        ("pk", "HASH"),
        ("sk", "RANGE"),
    ]
    assert props["BillingMode"] == "PROVISIONED"
    assert props["TableClass"] == "STANDARD"
    assert props["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is False
    assert "GlobalSecondaryIndexes" not in props


def test_the_checkpoints_table_is_3_3_with_the_savers_own_key_names() -> None:
    props = checkpoints_table_properties()
    assert props["TableName"] == {"Sub": "glean-agent-checkpoints-${Environment}"}
    assert props["ProvisionedThroughput"] == {"ReadCapacityUnits": 3, "WriteCapacityUnits": 3}
    assert props["TimeToLiveSpecification"] == {"AttributeName": "ttl", "Enabled": True}
    # LangGraph's DynamoDB saver writes `PK`/`SK`, upper case.
    assert [(key["AttributeName"], key["KeyType"]) for key in props["KeySchema"]] == [
        ("PK", "HASH"),
        ("SK", "RANGE"),
    ]
    assert "GlobalSecondaryIndexes" not in props


def test_the_queue_gives_up_on_a_message_after_two_attempts() -> None:
    queue = queue_properties("GleanAgentQueue")
    dead_letter = queue_properties("GleanAgentDeadLetterQueue")

    assert queue["VisibilityTimeout"] == 130
    assert queue["RedrivePolicy"] == {
        "deadLetterTargetArn": {"GetAtt": "GleanAgentDeadLetterQueue.Arn"},
        "maxReceiveCount": 2,
    }
    assert dead_letter["MessageRetentionPeriod"] == 1209600


def test_the_queue_outlives_the_worker_as_aws_requires() -> None:
    """cfn-lint E3505: the visibility timeout must be at least the function timeout (ADR 0026)."""
    worker = functions()["AgentWorkerFunction"]

    assert queue_properties("GleanAgentQueue")["VisibilityTimeout"] > worker["Timeout"]


def test_the_lease_sits_between_the_function_timeout_and_the_visibility_timeout() -> None:
    """The code's lease (store.LEASE_SECONDS) must be derivable from, and inside, these two numbers.

    Above the lambda timeout means a live run is never taken over inside its own invocation; below the
    visibility timeout means every redelivered copy of the message finds the lease lapsed, so a crashed
    run's work is picked up rather than acked away.
    """
    worker = functions()["AgentWorkerFunction"]
    queue = queue_properties("GleanAgentQueue")

    assert worker["Timeout"] == WORKER_TIMEOUT_SECONDS
    assert queue["VisibilityTimeout"] == QUEUE_VISIBILITY_SECONDS
    assert worker["Timeout"] < LEASE_SECONDS < queue["VisibilityTimeout"]


def test_the_template_suppresses_no_lint_rule() -> None:
    """A suppressed rule hides a deployment constraint; the queue/worker pairing has to satisfy it."""
    template = load(TEMPLATE)

    assert "Metadata" not in template or "cfn-lint" not in template.get("Metadata", {})


def test_the_worker_takes_one_message_at_a_time() -> None:
    worker = functions()["AgentWorkerFunction"]
    events = [event for event in worker["Events"].values() if event["Type"] == "SQS"]

    assert worker["Handler"] == "glean.worker.handler"
    assert worker["Timeout"] == 120
    assert [event["Properties"]["Queue"] for event in events] == [{"GetAtt": "GleanAgentQueue.Arn"}]
    assert events[0]["Properties"]["BatchSize"] == 1


def test_the_dead_letter_queue_has_its_own_handler() -> None:
    function = functions()["AgentDeadLetterFunction"]
    events = [event for event in function["Events"].values() if event["Type"] == "SQS"]

    assert function["Handler"] == "glean.worker.dlq_handler"
    assert [event["Properties"]["Queue"] for event in events] == [{"GetAtt": "GleanAgentDeadLetterQueue.Arn"}]


def test_the_worker_can_read_what_a_run_needs_and_nothing_more() -> None:
    policies = functions()["AgentWorkerFunction"]["Policies"]
    tables = [p["DynamoDBCrudPolicy"]["TableName"] for p in policies if "DynamoDBCrudPolicy" in p]
    buckets = [p["S3ReadPolicy"]["BucketName"] for p in policies if "S3ReadPolicy" in p]

    assert tables == [{"Ref": "GleanAgentSessionsTable"}, {"Ref": "GleanAgentCheckpointsTable"}]
    # The corpus is read from the recipe cache bucket; the receipts bucket is the API's business.
    assert buckets == [{"Ref": "GleanRecipeCacheBucket"}]
    assert not [p for p in policies if "S3CrudPolicy" in p]


def test_the_api_is_told_where_the_session_stack_is() -> None:
    api = functions()["GleanFunction"]["Environment"]["Variables"]
    worker = functions()["AgentWorkerFunction"]["Environment"]["Variables"]

    for name, reference in {
        "AGENT_SESSIONS_TABLE": {"Ref": "GleanAgentSessionsTable"},
        "AGENT_CHECKPOINTS_TABLE": {"Ref": "GleanAgentCheckpointsTable"},
        "AGENT_SESSION_QUEUE_URL": {"Ref": "GleanAgentQueue"},
        "AGENT_SESSION_TTL_HOURS": {"Ref": "AgentSessionTtlHours"},
    }.items():
        assert api[name] == reference
        assert worker[name] == reference


def test_the_worker_gets_the_same_environment_as_the_api() -> None:
    # The worker builds the same Settings object as the API, so a variable added to one and not the
    # other would only fail at run time, in Lambda. It never serves HTTP, so it may hold fewer.
    api = functions()["GleanFunction"]["Environment"]["Variables"]
    worker = functions()["AgentWorkerFunction"]["Environment"]["Variables"]

    assert set(api) <= set(worker)


def test_every_function_has_a_log_group_with_a_retention() -> None:
    resources: dict[str, Any] = load(TEMPLATE)["Resources"]
    log_groups = {
        name: resource["Properties"]
        for name, resource in resources.items()
        if resource["Type"] == "AWS::Logs::LogGroup"
    }

    for function in ("GleanFunction", "AgentWorkerFunction", "AgentDeadLetterFunction"):
        log_group = next(
            (
                properties
                for properties in log_groups.values()
                if properties.get("LogGroupName") == {"Sub": f"/aws/lambda/${{{function}}}"}
            ),
            None,
        )
        assert log_group is not None, function
        assert log_group["RetentionInDays"] > 0

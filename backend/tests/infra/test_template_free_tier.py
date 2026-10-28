"""ADR 0001: DynamoDB must stay inside the AWS free tier."""

from __future__ import annotations

from tests.infra.cfn import catalogue_table_properties, dynamo_table_properties, recipes_table_properties

FREE_TIER_RCU = 25
FREE_TIER_WCU = 25


def test_catalogue_capacity_summed_over_table_and_indexes_fits_the_free_tier() -> None:
    props = catalogue_table_properties()
    throughputs = [
        props["ProvisionedThroughput"],
        *(gsi["ProvisionedThroughput"] for gsi in props["GlobalSecondaryIndexes"]),
    ]
    assert sum(t["ReadCapacityUnits"] for t in throughputs) <= FREE_TIER_RCU
    assert sum(t["WriteCapacityUnits"] for t in throughputs) <= FREE_TIER_WCU


def test_catalogue_table_is_provisioned_standard_with_no_pitr_or_streams() -> None:
    props = catalogue_table_properties()
    assert props["BillingMode"] == "PROVISIONED"
    assert props["TableClass"] == "STANDARD"
    assert props["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is False
    assert "StreamSpecification" not in props


def test_capacity_summed_over_every_table_and_index_fits_the_free_tier() -> None:
    """Catalogue 10 + recipes 5 + sessions 2 + checkpoints 3 = 20 of the shared 25/25."""
    throughputs = [
        throughput
        for props in dynamo_table_properties().values()
        for throughput in [
            props["ProvisionedThroughput"],
            *(gsi["ProvisionedThroughput"] for gsi in props.get("GlobalSecondaryIndexes", [])),
        ]
    ]
    read = sum(t["ReadCapacityUnits"] for t in throughputs)
    write = sum(t["WriteCapacityUnits"] for t in throughputs)
    assert read == 20
    assert write == 20
    assert read <= FREE_TIER_RCU
    assert write <= FREE_TIER_WCU


def test_every_dynamodb_table_is_provisioned_standard_with_no_pitr_or_streams() -> None:
    # Billing mode and the absence of a stream are what keep an idle table at zero cost.
    for name, props in dynamo_table_properties().items():
        assert props["BillingMode"] == "PROVISIONED", name
        assert props["TableClass"] == "STANDARD", name
        assert props["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is False, name
        assert "StreamSpecification" not in props, name


def test_the_stack_declares_only_the_catalogue_recipes_and_agent_tables() -> None:
    assert sorted(dynamo_table_properties()) == [
        "GleanAgentCheckpointsTable",
        "GleanAgentSessionsTable",
        "GleanCatalogueTable",
        "GleanRecipesTable",
    ]


def test_the_recipes_table_is_5_5_with_no_gsis_and_no_pitr() -> None:
    props = recipes_table_properties()
    assert props["TableName"] == {"Sub": "glean-recipes-${Environment}"}
    assert props["ProvisionedThroughput"] == {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
    assert "GlobalSecondaryIndexes" not in props
    assert props["BillingMode"] == "PROVISIONED"
    assert props["TableClass"] == "STANDARD"
    assert props["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is False
    assert "StreamSpecification" not in props
    assert [(k["AttributeName"], k["KeyType"]) for k in props["KeySchema"]] == [("pk", "HASH"), ("sk", "RANGE")]

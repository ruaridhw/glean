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
    throughputs = [
        throughput
        for props in dynamo_table_properties().values()
        for throughput in [
            props["ProvisionedThroughput"],
            *(gsi["ProvisionedThroughput"] for gsi in props.get("GlobalSecondaryIndexes", [])),
        ]
    ]
    assert sum(t["ReadCapacityUnits"] for t in throughputs) <= FREE_TIER_RCU
    assert sum(t["WriteCapacityUnits"] for t in throughputs) <= FREE_TIER_WCU


def test_the_stack_declares_only_the_catalogue_and_recipes_tables() -> None:
    # Every new table is capacity taken from the same 25/25 budget, so adding one is a deliberate act.
    assert sorted(dynamo_table_properties()) == ["GleanCatalogueTable", "GleanRecipesTable"]


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

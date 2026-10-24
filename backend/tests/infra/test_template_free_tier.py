"""ADR 0001: DynamoDB must stay inside the AWS free tier."""

from __future__ import annotations

from tests.infra.cfn import catalogue_table_properties, dynamo_table_properties

FREE_TIER_RCU = 25
FREE_TIER_WCU = 25
# F1 (#162, open PR #194): the recipe store, 5/5. Delete these when it merges.
RECIPES_RESERVE_RCU = 5
RECIPES_RESERVE_WCU = 5


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
    """ADR 0001: the 25/25 budget is shared by every table and index in the region.

    Catalogue 10 + agent sessions 2 + agent checkpoints 3 = 15 of 25 on this branch. F1 (#162, open
    PR #194) adds the recipe store at 5/5, taking the account to 20/20. The reserve below counts it so
    a table that lands before that PR does not quietly overshoot; delete it when F1 merges.
    """
    throughputs = [
        throughput
        for props in dynamo_table_properties().values()
        for throughput in [
            props["ProvisionedThroughput"],
            *(gsi["ProvisionedThroughput"] for gsi in props.get("GlobalSecondaryIndexes", [])),
        ]
    ]
    read = sum(t["ReadCapacityUnits"] for t in throughputs) + RECIPES_RESERVE_RCU
    write = sum(t["WriteCapacityUnits"] for t in throughputs) + RECIPES_RESERVE_WCU

    assert read <= FREE_TIER_RCU
    assert write <= FREE_TIER_WCU


def test_every_dynamodb_table_is_provisioned_standard_with_no_pitr_or_streams() -> None:
    # Billing mode and the absence of a stream are what keep an idle table at zero cost.
    for name, props in dynamo_table_properties().items():
        assert props["BillingMode"] == "PROVISIONED", name
        assert props["TableClass"] == "STANDARD", name
        assert props["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is False, name
        assert "StreamSpecification" not in props, name

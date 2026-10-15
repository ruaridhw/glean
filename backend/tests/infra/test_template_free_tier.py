"""ADR 0001: DynamoDB must stay inside the AWS free tier."""

from __future__ import annotations

from tests.infra.cfn import TEMPLATE, catalogue_table_properties, load

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


def test_the_stack_declares_no_other_dynamodb_table() -> None:
    tables = [name for name, res in load(TEMPLATE)["Resources"].items() if res["Type"] == "AWS::DynamoDB::Table"]
    assert tables == ["GleanCatalogueTable"]

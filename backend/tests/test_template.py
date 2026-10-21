"""The SAM template read as data: what the deployed bucket and API gateway will do."""

from pathlib import Path
from typing import Any

import yaml

TEMPLATE = Path(__file__).parents[1] / "template.yaml"


def _load() -> dict[str, Any]:
    class Loader(yaml.SafeLoader):
        pass

    # CloudFormation short-form tags (!Ref, !Sub, !GetAtt ...) load as their plain value.
    def passthrough(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> Any:
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node)
        return loader.construct_mapping(node)

    Loader.add_multi_constructor("!", passthrough)
    return yaml.load(TEMPLATE.read_text(), Loader=Loader)  # noqa: S506


def _days_until_expiry(key: str) -> list[int]:
    """Expiry in days from every enabled receipts-bucket lifecycle rule that applies to ``key``."""
    rules = _load()["Resources"]["GleanReceiptsBucket"]["Properties"]["LifecycleConfiguration"]["Rules"]
    return [
        rule["ExpirationInDays"]
        for rule in rules
        if rule["Status"] == "Enabled" and key.startswith(rule.get("Prefix", ""))
    ]


def test_a_diagnostics_export_is_kept_for_about_thirty_days() -> None:
    assert _days_until_expiry("db-exports/user-sub/20261015T120000000000Z/glean.db") == [30]


def test_receipt_scans_still_expire_after_one_day() -> None:
    assert _days_until_expiry("receipts/tmp/3f2a.jpg") == [1]


def test_api_gateway_access_logs_go_to_a_log_group_the_template_creates() -> None:
    template = _load()
    settings = template["Globals"]["HttpApi"]["AccessLogSettings"]

    log_group = settings["DestinationArn"].split(".")[0]  # !GetAtt <logical id>.Arn
    assert template["Resources"][log_group]["Type"] == "AWS::Logs::LogGroup"
    assert template["Resources"][log_group]["Properties"]["RetentionInDays"] > 0


def test_api_gateway_access_log_format_never_records_credentials() -> None:
    fmt = _load()["Globals"]["HttpApi"]["AccessLogSettings"]["Format"].lower()

    assert "$context.requestid" in fmt
    assert "$context.status" in fmt
    assert "authorization" not in fmt
    assert "$request" not in fmt  # no request headers/body variables


def test_the_api_lambda_reads_its_paid_model_rate_limit_from_a_template_parameter() -> None:
    """Deployments raise the limit through CloudFormation, so no code change and no redeploy script edit is needed."""
    template = _load()
    parameter = template["Parameters"]["RateLimitPerHour"]
    assert parameter["Type"] == "Number"
    assert parameter["Default"] == 60
    assert parameter["Description"]

    variables = template["Resources"]["GleanFunction"]["Properties"]["Environment"]["Variables"]
    assert variables["RATE_LIMIT_PER_HOUR"] == "RateLimitPerHour"


def test_only_the_api_lambda_receives_the_rate_limit() -> None:
    template = _load()
    for name, resource in template["Resources"].items():
        if resource["Type"] != "AWS::Serverless::Function":
            continue
        variables = resource["Properties"].get("Environment", {}).get("Variables", {})
        if name != "GleanFunction":
            assert "RATE_LIMIT_PER_HOUR" not in variables, f"{name} does not pay for model calls"

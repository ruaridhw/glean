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

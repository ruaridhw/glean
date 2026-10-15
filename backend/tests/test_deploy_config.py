"""The prod deploy parameters live in one place: samconfig.toml. These tests pin that contract."""

from __future__ import annotations

import shlex
import tomllib
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[1]
WORKFLOWS = BACKEND.parent / ".github" / "workflows"


class _CfnLoader(yaml.SafeLoader):
    """Reads CloudFormation short-form tags (!Ref, !Sub, ...) as plain values."""


def _cfn_tag(loader: _CfnLoader, suffix: str, node: yaml.Node) -> object:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_mapping(node, deep=True)


_CfnLoader.add_multi_constructor("!", _cfn_tag)


def _template() -> dict:
    return yaml.load((BACKEND / "template.yaml").read_text(), Loader=_CfnLoader)  # noqa: S506 - subclass of SafeLoader


def _config_env(env: str) -> dict[str, str]:
    """samconfig's parameter_overrides for one config env, as a key -> value mapping."""
    config = tomllib.loads((BACKEND / "samconfig.toml").read_text())
    pairs = shlex.split(config[env]["deploy"]["parameters"]["parameter_overrides"])
    return dict(pair.split("=", 1) for pair in pairs)


def test_samconfig_carries_no_google_oauth_values() -> None:
    text = (BACKEND / "samconfig.toml").read_text()
    assert "google" not in text.lower()
    assert "PLACEHOLDER" not in text


def test_template_resolves_google_oauth_from_secrets_manager() -> None:
    template = _template()
    details = template["Resources"]["GoogleIdentityProvider"]["Properties"]["ProviderDetails"]
    assert "{{resolve:secretsmanager:glean/${Environment}/google-oauth-client-id:SecretString}}" in details["client_id"]
    assert (
        "{{resolve:secretsmanager:glean/${Environment}/google-oauth-client-secret:SecretString}}"
        in details["client_secret"]
    )
    assert not [name for name in template["Parameters"] if name.startswith("Google")]


def test_deploying_with_samconfig_alone_supplies_every_required_template_parameter() -> None:
    required = {name for name, spec in _template()["Parameters"].items() if "Default" not in spec}
    for env in ("prod", "dev"):
        assert required <= _config_env(env).keys(), env


def test_prod_samconfig_keeps_llm_tracing_on() -> None:
    assert _config_env("prod")["LangSmithTracing"] == "true"


def test_template_stamps_the_deployed_commit_onto_the_lambda() -> None:
    template = _template()
    assert template["Parameters"]["GitSha"]["Default"] == "unknown"
    assert template["Globals"]["Function"]["Environment"]["Variables"]["GIT_SHA"] == "GitSha"



def test_ci_deploys_through_the_shared_script_without_its_own_parameters() -> None:
    workflow = (WORKFLOWS / "backend-deploy.yml").read_text()
    assert "deploy_prod.py" in workflow
    assert "parameter-overrides" not in workflow
    assert "google" not in workflow.lower()

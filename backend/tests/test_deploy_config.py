"""The prod deploy parameters live in one place: samconfig.toml. These tests pin that contract."""

from __future__ import annotations

import shlex
import tomllib
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[1]
WORKFLOWS = BACKEND.parent / ".github" / "workflows"


class _CfnLoader(yaml.SafeLoader):
    """Reads CloudFormation short-form tags as their long-form intrinsic: `!Ref X` -> {"Ref": "X"}."""


def _cfn_tag(loader: _CfnLoader, suffix: str, node: yaml.Node) -> object:
    if isinstance(node, yaml.ScalarNode):
        value: object = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {"Ref" if suffix == "Ref" else f"Fn::{suffix}": value}


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
    assert details["client_id"] == {
        "Fn::Sub": "{{resolve:secretsmanager:glean/${Environment}/google-oauth-client-id:SecretString}}"
    }
    assert details["client_secret"] == {
        "Fn::Sub": "{{resolve:secretsmanager:glean/${Environment}/google-oauth-client-secret:SecretString}}"
    }
    assert not [name for name in template["Parameters"] if name.startswith("Google")]


def test_deploying_with_samconfig_alone_supplies_every_required_template_parameter() -> None:
    required = {name for name, spec in _template()["Parameters"].items() if "Default" not in spec}
    for env in ("prod", "dev"):
        assert required <= _config_env(env).keys(), env


def test_prod_samconfig_keeps_llm_tracing_on() -> None:
    assert _config_env("prod")["LangSmithTracing"] == "true"


def test_template_wires_the_git_sha_parameter_into_every_lambda_environment() -> None:
    template = _template()
    assert template["Parameters"]["GitSha"] == {"Type": "String", "Default": "unknown"}
    # Globals apply to every function, so a Ref here reaches the API Lambda and the trigger Lambda alike.
    assert template["Globals"]["Function"]["Environment"]["Variables"]["GIT_SHA"] == {"Ref": "GitSha"}
    for name, resource in template["Resources"].items():
        if resource["Type"] == "AWS::Serverless::Function":
            overrides = resource["Properties"].get("Environment", {}).get("Variables", {})
            assert "GIT_SHA" not in overrides, f"{name} would shadow the stamped GIT_SHA"


def test_ci_deploy_job_runs_the_shared_script_and_nothing_else_deploys() -> None:
    workflow = yaml.safe_load((WORKFLOWS / "backend-deploy.yml").read_text())
    job = workflow["jobs"]["deploy-prod"]
    runs = [step["run"] for step in job["steps"] if "run" in step]

    assert job["defaults"]["run"]["working-directory"] == "backend"
    assert [run.strip() for run in runs if "deploy_prod.py" in run] == ["python3 scripts/deploy_prod.py"]
    assert not [run for run in runs if "sam deploy" in run or "parameter-overrides" in run]
    assert not [run for run in runs if "google" in run.lower()]


def test_ci_deploy_checks_out_full_history_so_the_pushed_check_can_compare_ancestry() -> None:
    workflow = yaml.safe_load((WORKFLOWS / "backend-deploy.yml").read_text())
    checkout = next(
        s for s in workflow["jobs"]["deploy-prod"]["steps"] if s.get("uses", "").startswith("actions/checkout")
    )
    assert checkout.get("with", {}).get("fetch-depth") == 0

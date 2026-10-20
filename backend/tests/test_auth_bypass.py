import pytest

from glean.dependencies import local_auth_bypass_enabled


def test_a_locally_run_dev_backend_skips_token_checks() -> None:
    assert local_auth_bypass_enabled({"ENVIRONMENT": "dev"})


@pytest.mark.parametrize(
    "environ",
    [
        pytest.param({"ENVIRONMENT": "dev", "AWS_LAMBDA_FUNCTION_NAME": "glean-api-dev"}, id="deployed dev stage"),
        pytest.param({"ENVIRONMENT": "prod", "AWS_LAMBDA_FUNCTION_NAME": "glean-api-prod"}, id="deployed prod"),
        pytest.param({"ENVIRONMENT": "prod"}, id="local prod settings"),
        pytest.param({}, id="no environment"),
    ],
)
def test_every_other_backend_verifies_tokens(environ: dict[str, str]) -> None:
    assert not local_auth_bypass_enabled(environ)

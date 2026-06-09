from app.main import create_app
from behave import then, when
from fastapi.testclient import TestClient


def client() -> TestClient:
    return TestClient(create_app())


@when("I request the liveness endpoint")
def request_liveness(context):
    context.response = client().get("/health")


@when("I request the API health endpoint")
def request_api_health(context):
    context.response = client().get("/api/v1/health")


@then("the response status code is {status_code:d}")
def assert_status_code(context, status_code):
    assert context.response.status_code == status_code


@then("the response describes the xero-core service")
def assert_xero_core_service(context):
    payload = context.response.json()
    assert payload["service"] == "xero-core"
    assert payload["status"] == "ok"

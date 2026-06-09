Feature: Xero Core health endpoints
  Scenario: Liveness endpoint reports the backend service
    When I request the liveness endpoint
    Then the response status code is 200
    And the response describes the xero-core service

  Scenario: API-prefixed health endpoint requires authentication
    When I request the API health endpoint
    Then the response status code is 401

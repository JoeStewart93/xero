Feature: Split API service boundaries
  Scenario: BFF exposes local operator API only
    Given a test BFF service
    Then the BFF health endpoint reports the bff role
    And the BFF does not expose C2 beacon routes

  Scenario: C2 exposes C2 beacon API only
    Given a test C2 service
    When I connect to the C2 service
    And I register and heartbeat a beacon
    Then the C2 service lists the beacon as online
    And the C2 service does not expose BFF login routes

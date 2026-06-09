Feature: Operator websocket realtime
  Scenario: C2 operator websocket accepts authenticated clients
    Given a C2 realtime test service
    When I authenticate to the C2 service
    And I connect to the operator websocket
    Then the operator websocket receives a connected event

  Scenario: C2 beacon registration is available for realtime producers
    Given a C2 realtime test service
    When I authenticate to the C2 service
    And I register a beacon through the C2 API
    Then the C2 beacon list includes the registered beacon

  Scenario: C2 beacon registration returns one-time token material
    Given a C2 realtime test service
    When I register a beacon through the C2 API
    Then the beacon registration response includes token material

  Scenario: C2 beacon re-registration updates the existing fingerprint
    Given a C2 realtime test service
    When I authenticate to the C2 service
    And I register a beacon through the C2 API
    And I re-register the same beacon fingerprint with new metadata
    Then the C2 beacon list contains one updated beacon

  Scenario: C2 beacon heartbeat restores an offline beacon
    Given a C2 realtime test service
    When I authenticate to the C2 service
    And I register a beacon through the C2 API
    And I mark the registered beacon offline
    And I connect to the operator websocket
    And I send a heartbeat with the registered beacon token
    Then the operator websocket receives beacon recovery and heartbeat events

  Scenario: C2 beacon list filters online beacons
    Given a C2 realtime test service
    When I authenticate to the C2 service
    And I register a beacon through the C2 API
    Then the online beacon filter includes the registered beacon

  Scenario: Operator websocket rejects unauthenticated clients
    Given a C2 realtime test service
    When I connect to the operator websocket without a token
    Then the websocket is closed with code 4401

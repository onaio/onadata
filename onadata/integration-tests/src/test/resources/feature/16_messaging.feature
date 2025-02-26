@Messaging
  Feature: Messaging

    Scenario: Get event messages
      Given I am Testing Case : "5884"
      And I Set Get event messages
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for getting event messages

    Scenario: Get events for a specific verb
      Given I am Testing Case : "5885"
      And I Set Get events for a specific verb
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for getting events for a specific verb

    Scenario: Paginate events for a specific verb
      Given I am Testing Case : "5886"
      And I Set Paginate events for a specific verb
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for paginating events for a specific verb

    Scenario: Get messaging stats
      Given I am Testing Case : "5887"
      And I Set Get messaging stats
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for getting messaging stats


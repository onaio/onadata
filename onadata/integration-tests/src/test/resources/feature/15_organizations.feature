@Organizations
  Feature: Organizations
    
    Scenario: Register an organization
      Given I am Testing Case : "5875"
      And I Set Create an organization
      When  I Set request HEADER and PAYLOAD
      And Send a POST HTTP request
      Then I receive a valid Response for  creating an organization

    Scenario: Get list of organizations
      Given I am Testing Case : "5876"
      And I Set Get list of organizations
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for Get list of organizations

    Scenario: List organizations shared with another user
      Given I am Testing Case : "5877"
      And I Set list organizations shared with another user
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for listing organizations shared with another user

    Scenario: Retrieve organization profile information
      Given I am Testing Case : "5878"
      And I Set Retrieve organization profile information
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for retrieving organization profile information

    Scenario: Update organization profile
      Given I am Testing Case : "5879"
      And I Set Update organization profile
      When I Set request HEADER and PAYLOAD
      And Send a PATCH HTTP request
      Then I receive a valid Response for updating organization profile

    Scenario:  Add a user to an organization
      Given I am Testing Case : "5880"
      And I Set Add a user to an organization
      When I Set request HEADER and PAYLOAD
      And Send a POST HTTP request
      Then I receive a valid Response for adding a user to an organization

    Scenario: List organization members
      Given I am Testing Case : "5881"
      And I Set List organization members
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for listing organization members


    Scenario: Remove member from organization
      Given I am Testing Case : "5883"
      And I Set Remove member from organization
      When I Set request HEADER and PAYLOAD
      And Send a DELETE HTTP request
      Then I receive a valid Response for removing member from organization


@Profiles
  Feature: Profiles

    Scenario: Retrieve user profile information
      Given I am Testing Case : "5889"
      And I Set Retrieve user profile information
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for retrieving user profile information

    Scenario: Partial update of user information
      Given I am Testing Case : "5890"
      And I Set Partial update of user information
      When I Set request HEADER and PAYLOAD
      And Send a PATCH HTTP request
      Then I receive a valid Response for partial update of user information

    Scenario: Get number of monthly submissions
      Given I am Testing Case : "5891"
      And I Set Get total number of monthly submissions
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for getting total number of monthly submissions




@Users
  Feature: Users

    Scenario: Retrieve user profile
      Given I am Testing Case : "5898"
      And I Set Retrieve user profile
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Reponse for retrieving user profile

    Scenario: Get projects starred by user
      Given I am Testing Case : "5899"
      And I Set Get projects starred by user
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for getting projects starred by user

    Scenario: Get list of users
      Given I am Testing Case : "5900"
      And I Set Get list of users
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for getting list of users

    Scenario: Get list of users excluding organizations
      Given I am Testing Case : "5901"
      And I Set Get list of users excluding organizations
      When I Set request HEADER
      And Send a GET HTTP request
      Then  I receive a valid Response for getting list of users excluding organizations

    Scenario: Retrieve a specific user information
      Given I am Testing Case : "5902"
      And I Set Retrieve a specific user information
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for retrieving a specific user information

    Scenario: Search for user using email
      Given I am Testing Case : "5903"
      And I Set Search for user using email
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for searching for user using email

    @DELETE
    Scenario: Delete a Project
      Given I am Testing Case : "5831"
      And I Set Delete project api endpoint
      When I Set request HEADER
      And Send a DELETE HTTP request
      Then I receive a valid Response for Delete a project

@Teams
  Feature: Teams

    Scenario: Get list of teams
      Given I am Testing Case : "5892"
      And I Set Get list of teams
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for Get list of teams

    Scenario: Filter team by organization
      Given I am Testing Case : "5893"
      And I Set Filter team by organization
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for filtering teams by organization

    Scenario: Filter team by id
      Given I am Testing Case : "5894"
      And I Set Filter team by id "<teamid>"
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for filtering a team by id

    Scenario: Add a user to a team
      Given I am Testing Case : "5895"
      And I Set Add a user to a team "<teamid>"
      When I Set request HEADER and PAYLOAD
      And Send a POST HTTP request
      Then I receive a valid Response for adding a user to a team

    Scenario: List members of a team
      Given I am Testing Case : "5896"
      And I Set List members of a team "<teamid>"
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for listing members of a team


    Scenario: Set team member permission on project
      Given I am Testing Case : "5897"
      And I Set team member permission on project "<teamid>"
      When  I Set request HEADER and PAYLOAD
      And Send a POST HTTP request
      Then I receive a valid Response for setting team member permission on project

    Scenario: Remove team member from team
      Given I am Testing Case : "5904"
      And I Set remove team member from team "<teamid>"
      When I Set request HEADER and PAYLOAD
      And Send a DELETE HTTP request
      Then I receive a valid Response for removing team member from team


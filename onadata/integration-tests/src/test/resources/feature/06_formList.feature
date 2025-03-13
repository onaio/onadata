@FormList
Feature: FormList

  @GET
  Scenario: GET list of forms in an account
    Given I am Testing Case : "2282"
    And I Set Get list of Forms in account api endpoint
    When I Set Digest Auth
    And Send a GET HTTP request
    Then I receive valid Response for Get list of Forms in account

@GET
Scenario: GET a specific form
  Given I am Testing Case : "2283"
  And I Set Get a specific form api endpoint
  When I Set Digest Auth
  And Send a GET HTTP request
  Then I receive valid Response for Get a specific form

@GET
Scenario: Filter forms with enketo
  Given I am Testing Case : "2284"
  And I Set filter Forms with enketo api endpoint
  When I Set Digest Auth
  And Send a GET HTTP request
  Then I receive valid Response for filter Forms with enketo preview

@GET
Scenario: Filter forms with enketo preview
  Given I am Testing Case : "2285"
  And I Set filter Forms with enketo preview api endpoint
  When I Set Digest Auth
  And Send a GET HTTP request
  Then I receive valid Response for filter Forms with enketo preview

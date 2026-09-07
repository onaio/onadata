@Widgets
Feature: Widgets

  @POST
  Scenario: Create a widget
    Given I am Testing Case : "2291"
    And I Set POST Widget service api endpoint
    When I Set request HEADER and PAYLOAD
    And Send a POST HTTP request
    Then I receive valid Response for POST Widget service

  @GET
  Scenario: Get a widget
    Given I am Testing Case : "2292"
    And I Set Get widget api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for Get widget api endpoint

  @GET
  Scenario: Get list of widgets
    Given I am Testing Case : "2293"
    And I Set Get list of Widgets api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then  I receive valid Response for Get list of Widgets api endpoint

  @PUT
  Scenario: Update a widget
    Given I am Testing Case : "2294"
    And I Set PUT update widget service api endpoint
    When I Set request HEADER and PAYLOAD
    And Send a PUT HTTP request
    Then I receive valid Response for update widget service

  @PATCH
  Scenario: Patch a widget
    Given I am Testing Case : "2295"
    And I Set PATCH a widget service api endpoint
    When I Set request HEADER and PAYLOAD
    And Send a PATCH HTTP request
    Then I receive valid Response for patch a widget service

  @GET
  Scenario: Get widgets data
    Given I am Testing Case : "2296"
    And I Set GET Widgets data service api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for Get Widgets data service

  @GET
  Scenario: Get widget with valid key
    Given I am Testing Case : "2297"
    And I Set GET widget with valid key api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for Get widget with valid key service

  @GET
  Scenario: Filter widget with formid
    Given I am Testing Case : "2298"
    And I Set filter widget by formid api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for filter widget by formid key service


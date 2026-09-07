@Charts
  Feature: Charts

    @Get
    Scenario: Read Charts
      Given I am Testing Case : "802"
      And I Set Get charts accessible by user api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for get charts accessible by user api endpoint

    @Get
    Scenario: Get a list of chart field endpoints for a specific form
      Given I am Testing Case : "803"
      And I Set Get chart fields for specific form api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for get chart fields for specific form api endpoint

    @Get
    Scenario: Get a chart for a specific field in a form
      Given I am Testing Case : "804"
      And I Set Get chart for specific field api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for get chart for specific field api endpoint

    @Get
    Scenario: Get a chart data for all fields in a form
      Given I am Testing Case : "805"
      And I Set Get chart data for all fields api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for get chart data for all fields api endpoint

    @GET
    Scenario: Get chart field grouped by another field
      Given I am Testing Case : "3925"
      And I Set Get chart field grouped by another field
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for chart field grouped by another field

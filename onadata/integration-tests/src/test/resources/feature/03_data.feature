@Data
Feature: Data

  @GET
  Scenario: Read Data
    Given I am Testing Case : "778"
    And I Set GET Data service api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data service

  @GET
  Scenario:GET JSON List of data end points using start value
    Given I am Testing Case : "779"
    And I Set GET Data service using start value api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data  using start value service

    @GET
  Scenario: GET JSON List of data end points using start and limit values
      Given I am Testing Case : "780"
      And I Set GET Data service using start and limit values api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for GET Data  using start and limit values service

  @GET
  Scenario: Pull data for all forms in CSV format
    Given I am Testing Case : "781"
    And I Set GET Data service for all Forms in CSV format api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data for all Forms in CSV formate service


  @GET
  Scenario: Pull data for specific form in CSV format
    Given I am Testing Case : "782"
    And I Set GET Data service for specific form in CSV format api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data for specific form in CSV format service


  @GET
  Scenario: GET JSON List of data end points filter by owner
    Given I am Testing Case : "783"
    And I Set GET Data service filter by owner api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data filter by owner service


  @GET
  Scenario: GET JSON list of submitted data for a specific form
    Given I am Testing Case : "784"
    And I Set GET JSON list of submitted data for a specific form api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for JSON list of submitted data for a specific form service


  @GET
  Scenario:GET XML list of submitted data for a specific form
    Given I am Testing Case : "785"
    And I Set GET XML list of submitted data for a specific form api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET XML list of submitted data for a specific form service

  @GET
  Scenario:Paginate data of a specific form
    Given I am Testing Case : "786"
    And I Set GET Paginate data of a specific form api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Paginate data of a specific form service

  @GET @test
  Scenario:Sort submitted data of a specific form in ascending order
    Given I am Testing Case : "787"
    And I Set GET Sort submitted data of a specific form in ascending order api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Sort submitted data of a specific form in ascending order service

  @GET @test
  Scenario:Sort submitted data of a specific form in descending order
    Given I am Testing Case : "788"
    And I Set GET ort submitted data of a specific form in descending order api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Sort submitted data of a specific form in descending order service


  @GET
  Scenario:Fetch data on select columns for a given form
    Given I am Testing Case : "790"
    And I Set GET Data on select columns for a given form api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data on select columns for a given form


  @GET @test
  Scenario:Query submissions with APPROVED submission review status
    Given I am Testing Case : "792"
    And I Set GET Query submissions with APPROVED submission review status api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Query submissions with APPROVED submission review status service


  @GET @test
  Scenario:Query submissions with REJECTED submission review status
    Given I am Testing Case : "793"
    And I Set GET query submissions with REJECTED submission review status api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET query submissions with REJECTED submission review status service


  @GET @test
  Scenario:Query submissions with PENDING submission review status
    Given I am Testing Case : "794"
    And I Set GET Query submissions with PENDING submission review status api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Query submissions with PENDING submission review status service


  @GET @test
  Scenario:Query submissions with pending submission review status or NULL
    Given I am Testing Case : "795"
    And I Set GET Query submissions with pending submission review status or NULL api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Query submissions with pending submission review status or NULL service
    
  @GET @test
  Scenario:Query submissions with NULL submission review status
    Given I am Testing Case : "796"
    And I Set GET Query submissions with NULL submission review status api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Query submissions with NULL submission review status service

  @GET @test
  Scenario:Query submitted data of a specific form using date_created
    Given I am Testing Case : "797"
    And I Set GET Data of a specific form using date_created api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET of a specific form using date_created service

  @GET @test
  Scenario:Query submitted data of a specific form using date_modified
    Given I am Testing Case : "798"
    And I Set GET Data of a specific form using date_modified api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data of a specific form using date_modified service

  @GET @test
  Scenario:Query submitted data of a specific form using last_edited
    Given I am Testing Case : "799"
    And I Set GET Data of a specific form using last_edited api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data of a specific form using last_edited service


  @GET @test
  Scenario:Get list of public data endpoints
    Given I am Testing Case : "800"
    And I Set GET list of public data api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET list of public data service







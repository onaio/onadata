@MergedDatasets
  Feature: MergedDatasets
    
    Scenario: Upload a second form
      Given I am Testing Case : "5859"
      And I Set upload another test form
      When I Set formupload2 request HEADER
      And Send a POST HTTP request
      Then I receive a valid Response for uploading a test form

    @POST
    Scenario: Import data via CSV
      Given I am Testing Case : "926"
      And I Set import data service api endpoint
      When I Set csvmultipart request HEADER
      And Send a POST HTTP request
      Then I receive valid Response for importing data service
    
    Scenario: Create merged dataset
      Given I am Testing Case : "2286"
      And I Set POST merge datasets api endpoint
      When I Set request HEADER and PAYLOAD
      And Send a POST HTTP request
      Then I receive valid Response for merge datasets service

    Scenario:  GET a merged dataset api endpoint
      Given I am Testing Case : "2287"
      And I Set GET merged dataset api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get merged dataset service
      
    Scenario: GET all merged datasets
      Given I am Testing Case : "2288"
      And I Set GET all merged datasets api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get all merged datasets service

    Scenario: GET data in merged datasets
      Given I am Testing Case : "2289"
      And I Set GET data in merged datasets api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get data in merged datasets service



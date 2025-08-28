@Metadata
  Feature: Metadata
    
    Scenario: Create a metadata
      Given I am Testing Case : "5868"
      And I Set Create metadata
      When I Set request HEADER and PAYLOAD
      And Send a POST HTTP request
      Then I receive a valid Response for Create metadata
    
    
    Scenario: GET form metadata api endpoint
      Given I am Testing Case : "2321"
      And I Set GET form metadata api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get form metadata service

    Scenario: GET specific metadata api endpoint
      Given I am Testing Case : "2322"
      And I Set GET specific metadata api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get specific metadata service


    Scenario: Delete metadata
      Given I am Testing Case : "5869"
      And I Set Delete metadata
      When I Set request HEADER
      And Send a DELETE HTTP request
      Then I receive a valid Response for deleting metadata

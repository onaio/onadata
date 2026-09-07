@RestServices
  Feature: RestServices

    Scenario: Add a rest service
      Given I am Testing Case : "5870"
      And I Set Add a rest service
      When I Set request HEADER and PAYLOAD
      And Send a POST HTTP request
      Then I receive a valid Response for adding a rest service
    
    
    Scenario: List rest services
      Given I am Testing Case : "3932"
      And I Set Get a list of all rest services
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for Get a list of rest services

    Scenario: List a specific rest service
      Given I am Testing Case : "3933"
      And I Set Get a specific rest service
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for getting a specific rest service

    Scenario: Delete a rest service
      Given I am Testing Case : "5871"
      And I Set Delete a rest service
      When  I Set request HEADER
      And Send a DELETE HTTP request
      Then I receive a valid Response for deleting a rest service

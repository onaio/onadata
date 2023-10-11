@Reviews
  Feature: Reviews
    
    Scenario: Make a submission review
      Given I am Testing Case : "969"
      And I Set POST make submission review api endpoint
      When I Set request HEADER and PAYLOAD
      And Send a POST HTTP request
      Then I receive valid Response for make submission review service
      
    Scenario: GET a submission review
      Given I am Testing Case : "972"
      And I Set GET submission review api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get submission review service
      
    Scenario: Get list of submission reviews
      Given I am Testing Case : "973"
      And I Set Get list of submission reviews
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for getting list of submission reviews
      
    Scenario: Filter reviews by instance
      Given I am Testing Case : "5866"
      And I Set filter reviews by instance
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for filter reviews by instance

    Scenario: Filter reviews by status
      Given I am Testing Case : "5867"
      And I Set filter reviews by status
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for filtering reviews by status



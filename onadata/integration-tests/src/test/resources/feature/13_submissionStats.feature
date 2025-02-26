@SubmissionStats
  Feature: SubmissionStats
    
    Scenario: GET submission stats api endpoint
      Given I am Testing Case : "2324"
      And I Set GET submission stats api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get submission stats service

    Scenario: Get Stats Summary
      Given I am Testing Case : "5873"
      And I Set Get Stats Summary
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for getting Stats Summary

    Scenario: Get specific stats
      Given I am Testing Case : "5874"
      And I Set Get specific stats
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive a valid Response for getting specific stats

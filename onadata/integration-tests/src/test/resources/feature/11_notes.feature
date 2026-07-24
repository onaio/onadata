@Notes
  Feature: Notes
    
    Scenario: Add a note 
      Given I am Testing Case : "2312"
      And I Set Add a note to a submission
      When  I Set request HEADER and PAYLOAD
      And Send a POST HTTP request
      Then I receive a valid Response for adding a note
    
    Scenario: Get list of notes api endpoint
      Given I am Testing Case : "2310"
      And I Set Get list of notes api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get list of notes service

    Scenario: Get notes in submission api endpoint
      Given I am Testing Case : "2311"
      And I Set Get notes in submission api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get notes in submission service
      
    Scenario: Delete a note
      Given I am Testing Case : "2313"
      And I Set Delete a note
      When I Set request HEADER
      And Send a DELETE HTTP request
      Then I receive a valid Response for deleting a note


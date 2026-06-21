@FilteredDatasets
  Feature: FilteredDatasets
    
    Scenario: Create a filtered dataset
      Given I am Testing Case : "956"
      And I Set POST filtered dataset api endpoint
      When I Set request HEADER and PAYLOAD
      And Send a POST HTTP request
      Then I receive valid Response for create filtered datasets service

    Scenario: GET filtered dataset api endpoint
      Given I am Testing Case : "957"
      And I Set GET filtered dataset api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get filtered dataset service

    Scenario: Update filtered dataset api endpoint
      Given I am Testing Case : "959"
      And I Set update filtered dataset api endpoint
      When I Set request HEADER and PAYLOAD
      And Send a PUT HTTP request
      Then I receive valid Response for update filtered dataset service

    Scenario: Patch filtered dataset api endpoint
      Given I am Testing Case : "960"
      And I Set Patch filtered dataset api endpoint
      When I Set request HEADER and PAYLOAD
      And Send a PATCH HTTP request
      Then I receive valid Response for patch filtered dataset service

    Scenario: GET data from filtered dataset
      Given I am Testing Case : "962"
      And I Set GET data from filtered dataset api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get data from filtered dataset service

    Scenario: GET filtered data using limit operators
      Given I am Testing Case : "963"
      And I Set GET filtered data using limit operators
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get filtered data using limit operators

    Scenario: GET filtered data using start limit operators
      Given I am Testing Case : "964"
      And I Set GET filtered data using start limit operators
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get filtered data using start limit operators
      
    Scenario: Count data in a filtered dataset 
      Given I am Testing Case : "965"
      And I Set count data in filtered dataset api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for count data in filtered dataset

    Scenario: Export data in a filtered dataset
      Given I am Testing Case : "966"
      And I Set export data in dataset api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for export data in dataset
      
    Scenario: Get charts in dataset api endpoint
      Given I am Testing Case : "967"
      And I Set Get charts in dataset api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get charts in dataset
      
    Scenario: Get chart field in dataset api endpoint
      Given I am Testing Case : "968"
      And I Set Get chart field in dataset api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get chart field in dataset
      
    Scenario: Delete a filtered dataset
      Given I am Testing Case : "961"
      And I Set Delete a filtered dataset
      When I Set request HEADER
      And Send a DELETE HTTP request
      Then I receive a valid Response for deleting a filtered dataset


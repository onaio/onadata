@Media
  Feature: Media
    
    Scenario: Upload a test form
      And I Set upload a test form
      When I Set testform request HEADER
      And Send a POST HTTP request
      Then I receive a valid Response for uploading test form

    Scenario: POST XML submission
      Given I am Testing Case : "821"
      And I Set Post XML submission
      When I Set XMLSubmission request HEADER
      And Send a POST HTTP request
      Then I receive a valid Response for posting xml submission

    Scenario: Get media files in a form api endpoint
      Given I am Testing Case : "2305"
      And I Set Get media files in a form api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get media files in a form service

    Scenario: Paginate media files api endpoint 
      Given I am Testing Case : "2302"
      And I Set paginate media files api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for paginate media files service
      
    Scenario: Get details of an attachment
      Given I am Testing Case : "2303"
      And I Set Get details of an attachment api endpoint with mediaid "<mediaid>"
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get details of an attachment

    Scenario: Get a specific media file
      Given I am Testing Case : "2304"
      And I Set Get a specific media file api endpoint "<mediaid>"
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get a specific media file

    Scenario: Get media file of a specific instance
      Given I am Testing Case : "2306"
      And I Set Get media file of a specific instance api endpoint "<instance>"
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get media of a specific instance

    Scenario: Filter media files by type
      Given I am Testing Case : "2307"
      And I Set Filter media files by type api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for filter media by type


    Scenario: Get image link of attachment
      Given I am Testing Case : "2308"
      And I Set Get image link of attachment api endpoint "<mediaid>" "<filename>"
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get image link of attachment

    Scenario: Get form media count api endpoint
      Given I am Testing Case : "2309"
      And I Set Get form media count api endpoint
      When I Set request HEADER
      And Send a GET HTTP request
      Then I receive valid Response for Get form media count service


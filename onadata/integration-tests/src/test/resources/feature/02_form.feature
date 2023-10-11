@Forms
Feature: Forms
  
  @POST
  Scenario: Replace a form
    Given I am Testing Case : "5852"
    And I Set replace form api endpoint
    When I Set formreplacement request HEADER
    And Send a PATCH HTTP request
    Then I receive a valid Response for replacing a form

  @POST
  Scenario: Import data via CSV
  Given I am Testing Case : "926"
  And I Set Post import data service api endpoint
  When I Set csvmultipart request HEADER
  And Send a POST HTTP request
  Then I receive valid Response for import data service

  @GET
  Scenario: GET all data exports
    Given I am Testing Case : "937"
    And I Set GET all Data exports api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET all Data exports

  @GET
  Scenario: GET form exports
    Given I am Testing Case : "938"
    And I Set GET form exports api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET form exports

  @GET
  Scenario: GET data export in csv
    Given I am Testing Case : "939"
    And I Set GET Data export in csv api endpoint
    When  I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data export in csv

  @GET
  Scenario: GET data export in xls
    Given I am Testing Case : "940"
    And I Set GET Data export in xls api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data export in xls

  @GET
  Scenario: GET data export in csvzip
    Given I am Testing Case : "941"
    And I Set GET Data export in csvzip api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data export in csvzip

  @GET
  Scenario: GET data export in sav
    Given I am Testing Case : "942"
    And I Set GET Data export in sav api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET Data export in sav

  @GET
  Scenario: GET list of forms
    Given I am Testing Case : "943"
    And I Set GET list of Forms api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for GET list of Forms service

  @GET
   Scenario: GET form xml representation
     Given I am Testing Case : "944"
     And I Set GET form xml representation api endpoint
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive valid Response for GET form xml representation service

   @GET
   Scenario: GET form json representation
     Given I am Testing Case : "945"
     And I Set GET form json representation api endpoint
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive valid Response for GET form json representation service

   @GET
   Scenario: GET xlsform representation
     Given I am Testing Case : "946"
     And I Set GET xlsform representation api endpoint
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive valid Response for GET xlsform representation service

   @POST
   Scenario: Add tags to a form
     Given I am Testing Case : "947"
     And I Set add tags to a form api endpoint
     When I Set request HEADER and PAYLOAD
     And Send a POST HTTP request
     Then I receive valid Response for add tags to a form

   @GET
   Scenario: GET form tags
     Given I am Testing Case : "948"
     And I Set GET form tags api endpoint
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive valid Response for GET form tags service

   @GET
   Scenario: GET form with specific tags
     Given I am Testing Case : "949"
     And I Set GET form with specific tags api endpoint
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive valid Response for GET form with specific tags service

   @GET
   Scenario: GET Enketo urls
     Given I am Testing Case : "951"
     And I Set GET form enketo urls api endpoint
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive valid Response for GET form enketo urls service

   @GET
   Scenario: GET single submission url
     Given I am Testing Case : "952"
     And I Set GET single submission url api endpoint
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive valid Response for GET single submission url service

   @GET
   Scenario: GET CSV data
     Given I am Testing Case : "953"
     And I Set GET form csv data api endpoint
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive valid Response for GET form csv data service

   @GET
   Scenario: GET xls data
     Given I am Testing Case : "954"
     And I Set GET form xls data api endpoint
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive valid Response for GET form xls data service

   @GET
   Scenario: GET form versions
     Given I am Testing Case : "955"
     And I Set GET form versions api endpoint
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive valid Response for GET form versions service

   @GET
   Scenario: Filter forms by owner
     Given I am Testing Case : "4579"
     And I Set filter forms by owner
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive a valid Response for filtering forms by owner

   @GET
   Scenario: Paginate a list of forms
     Given I am Testing Case : "4580"
     And I Set paginate list of forms
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive a valid Response for paginating list of forms

   @GET
   Scenario: Get form information
     Given I am Testing Case : "4581"
     And I Set Get form information
     When I Set request HEADER
     And Send a GET HTTP request
     Then I receive a valid Response for getting form information

   @POST
   Scenario: Clone a form
     Given I am Testing Case : "5853"
     And I Set clone a form api endpoint
     When I Set request HEADER and FORMDATA
     And Send a POST HTTP request
     Then I receive a valid Response for cloning a form

   @DELETE
   Scenario: Delete cloned form
     Given I am Testing Case : "5858"
     And I Set Delete cloned form
     When I Set request HEADER
     And Send a DELETE HTTP request
     Then I receive a valid Response for deleting cloned form









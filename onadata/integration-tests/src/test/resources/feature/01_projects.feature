@Projects

Feature: Projects

  @Post
  Scenario: Create a new project
    Given I am Testing Case : "975"
    And I Set Create a new project
    When I Set request HEADER and PAYLOAD
    And Send a POST HTTP request
    Then I receive a valid Response for Create new project

  @Get
  Scenario: Get projects
    Given I am Testing Case : "976"
    And I Set Get list of projects api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for Get list of projects

  @Get
  Scenario: Get projects by owner
    Given I am Testing Case : "977"
    And I Set Get list of projects by owner api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for Get list of projects by owner

  @Get
  Scenario: Get project information
    Given I am Testing Case : "978"
    And I Set Get project information api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for Get project information

  @PUT
  Scenario: Update a project
  Given I am Testing Case : "822"
  And I Set update a project api endpoint
  When I Set request HEADER and PAYLOAD
  And Send a PUT HTTP request
  Then I receive valid Response for update a project


  @PUT
  Scenario: Share a project
    Given I am Testing Case : "979"
    And I Set share a project api endpoint
    When I Set request HEADER and FORMDATA
    And Send a PUT HTTP request
    Then I receive valid Response for share a project

    @PUT
    Scenario: Share project with multiple users
      Given I am Testing Case : "5850"
      And I Set share a project with multiple users api endpoint
      When I Set request HEADER and FORMDATA
      And Send a PUT HTTP request
      Then I receive valid Response for share a project with multiple users

  @PUT
   Scenario: Send email on sharing a project
    Given I am Testing Case : "5850"
    And I send email on sharing a project
    When I Set request HEADER and FORMDATA
    And Send a PUT HTTP request
    Then I receive a valid Response for send email

  @PUT
  Scenario: Remove a user
    Given I am Testing Case : "980"
    And I Set remove a user api endpoint
    When I Set request HEADER and FORMDATA
    And Send a PUT HTTP request
    Then I receive valid Response for remove a user

  @POST
  Scenario: Upload a form
    Given I am Testing Case : "5851"
    And I Set upload a form to the project
    When I Set formupload request HEADER
    And Send a POST HTTP request
    Then I receive a valid Response for uploading a form

  @POST
  Scenario: Assign a form
    Given I am Testing Case : "981"
    And I Set assign a form api endpoint
    When I Set request HEADER and PAYLOAD
    And Send a POST HTTP request
    Then I receive valid Response for assign a form

  @GET
  Scenario: Fetch forms in a project
    Given I am Testing Case : "982"
    And I Set Get Forms in a project api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for Get Forms in a project

  @POST
  Scenario: Add tags to a project
    Given I am Testing Case : "983"
    And I Set tag a project api endpoint
    When I Set request HEADER
    And Send a POST HTTP request
    Then I receive valid Response for tag a project

  @GET
  Scenario: Get project tags
    Given I am Testing Case : "984"
    And I Set Get project tags api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for Get project tags

  @GET
  Scenario: Filter project by tags
    Given I am Testing Case : "985"
    And I Set filter project by tags api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for filter project by tags

  @POST
  Scenario: Star a project
    Given I am Testing Case : "986"
    And I Set star a project api endpoint
    When I Set request HEADER
    And Send a POST HTTP request
    Then I receive valid Response for star a project

  @GET
  Scenario: Fetch starred projects
    Given I am Testing Case : "988"
    And I Set Get starred projects api endpoint
    When I Set request HEADER
    And Send a GET HTTP request
    Then I receive valid Response for Get starred projects

  @DELETE
  Scenario: Remove a star
    Given I am Testing Case : "987"
    And I Set remove a star api endpoint
    When I Set request HEADER
    And Send a DELETE HTTP request
    Then I receive valid Response for remove a star








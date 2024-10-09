package stepdefs;


import config.EndpointURLs;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;

import static stepdefs.Hooks.endPoint;

public class Users {
    @Given("I Set Retrieve user profile")
    public void iSetRetrieveUserProfile() {
        endPoint = EndpointURLs.RETRIEVE_USER_PROFILE;
    }

    @Then("I receive a valid Reponse for retrieving user profile")
    public void iReceiveAValidReponseForRetrievingUserProfile() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        
    }

    @Given("I Set Get projects starred by user")
    public void iSetGetProjectsStarredByUser() {
        endPoint = EndpointURLs.GET_PROJECTS_STARRED_BY_USER;
    }


    @Then("I receive a valid Response for getting projects starred by user")
    public void iReceiveAValidResponseForGettingProjectsStarredByUser() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        
    }

    @Given("I Set Get list of users")
    public void iSetGetListOfUsers() {
        endPoint = EndpointURLs.LIST_USERS;
    }

    @Then("I receive a valid Response for getting list of users")
    public void iReceiveAValidResponseForGettingListOfUsers() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        
    }

    @Given("I Set Get list of users excluding organizations")
    public void iSetGetListOfUsersExcludingOrganizations() {
        endPoint = EndpointURLs.LIST_USERS_EXCLUDING_ORGS;
    }

    @Then("I receive a valid Response for getting list of users excluding organizations")
    public void iReceiveAValidResponseForGettingListOfUsersExcludingOrganizations() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        
    }

    @Given("I Set Retrieve a specific user information")
    public void iSetRetrieveASpecificUserInformation() {
        endPoint = EndpointURLs.GET_SPECIFIC_USER_INFO;
    }

    @Then("I receive a valid Response for retrieving a specific user information")
    public void iReceiveAValidResponseForRetrievingASpecificUserInformation() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        
    }

    @Given("I Set Search for user using email")
    public void iSetSearchForUserUsingEmail() {
        endPoint = EndpointURLs.SEARCH_FOR_USER_USING_EMAIL;
    }

    @Then("I receive a valid Response for searching for user using email")
    public void iReceiveAValidResponseForSearchingForUserUsingEmail() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }
}

package stepdefs;

import config.EndpointURLs;

import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;
import payloads.ProfilePayload;

import static stepdefs.Hooks.RequestPayLoad;
import static stepdefs.Hooks.endPoint;

public class Profiles {
    @Given("I Set Register a user")
    public void iSetRegisterAUser() {
    }

    @Then("I receive a valid Response for registering a user")
    public void iReceiveAValidResponseForRegisteringAUser() {
        
    }

    @Given("I Set Retrieve user profile information")
    public void iSetRetrieveUserProfileInformation() {
        endPoint = EndpointURLs.GET_USER_PROFILE_INFO;
    }

    @Then("I receive a valid Response for retrieving user profile information")
    public void iReceiveAValidResponseForRetrievingUserProfileInformation() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Partial update of user information")
    public void iSetPartialUpdateOfUserInformation() {
        endPoint = EndpointURLs.UPDATE_USER_INFO;
        RequestPayLoad = ProfilePayload.updateProfile();
    }

    @Then("I receive a valid Response for partial update of user information")
    public void iReceiveAValidResponseForPartialUpdateOfUserInformation() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        
    }

    @Given("I Set Get total number of monthly submissions")
    public void iSetGetTotalNumberOfMonthlySubmissions() {
        endPoint = EndpointURLs.GET_MONTHLY_SUBMISSIONS;
    }

    @Then("I receive a valid Response for getting total number of monthly submissions")
    public void iReceiveAValidResponseForGettingTotalNumberOfMonthlySubmissions() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }
}

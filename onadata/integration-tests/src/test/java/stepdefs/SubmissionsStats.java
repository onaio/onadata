package stepdefs;

import config.EndpointURLs;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;

import static config.EnvGlobals.getFormID;
import static stepdefs.Hooks.endPoint;

public class SubmissionsStats {
    @Given("I Set GET submission stats api endpoint")
    public void i_Set_Get_submission_stats_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_SUBMISSION_STATS.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for Get submission stats service")
    public void i_receive_valid_Response_for_Get_submission_stats_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get Stats Summary")
    public void iSetGetStatsSummary() {
        endPoint = String.format(EndpointURLs.GET_STATS_SUMMARY + getFormID);
    }

    @Then("I receive a valid Response for getting Stats Summary")
    public void iReceiveAValidResponseForGettingStatsSummary() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set Get specific stats")
    public void iSetGetSpecificStats() {
        endPoint = String.format(EndpointURLs.GET_SPECIFIC_STATS.replace("{id}", getFormID));
    }

    @Then("I receive a valid Response for getting specific stats")
    public void iReceiveAValidResponseForGettingSpecificStats() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

}

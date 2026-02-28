package stepdefs;

import config.EndpointURLs;

import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;

import static config.EnvGlobals.getFormID;
import static stepdefs.Hooks.endPoint;

public class Messaging {
    
    @Given("I Set Get event messages")
    public void iSetGetEventMessages() {
        endPoint = String.format(EndpointURLs.GET_EVENT_MESSAGES + getFormID);
    }

    @Then("I receive a valid Response for getting event messages")
    public void iReceiveAValidResponseForGettingEventMessages() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }


    @Given("I Set Get events for a specific verb")
    public void iSetGetEventsForASpecificVerb() {
        endPoint = String.format(EndpointURLs.GET_EVENTS_FOR_SPECIFIC_VERB.replace("{id}", getFormID));
    }


    @Then("I receive a valid Response for getting events for a specific verb")
    public void iReceiveAValidResponseForGettingEventsForASpecificVerb() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        
    }

    @Given("I Set Paginate events for a specific verb")
    public void iSetPaginateEventsForASpecificVerb() {
        endPoint = String.format(EndpointURLs.PAGINATE_EVENTS_FOR_A_VERB.replace("{id}", getFormID));
    }

    @Then("I receive a valid Response for paginating events for a specific verb")
    public void iReceiveAValidResponseForPaginatingEventsForASpecificVerb() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        
    }

    @Given("I Set Get messaging stats")
    public void iSetGetMessagingStats() {
        endPoint = String.format(EndpointURLs.GET_MESSAGING_STATS.replace("{id}", getFormID));
    }

    @Then("I receive a valid Response for getting messaging stats")
    public void iReceiveAValidResponseForGettingMessagingStats() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }
}

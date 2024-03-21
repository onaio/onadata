package stepdefs;


import config.EndpointURLs;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;
import payloads.RestServicesPayload;
import validation.RestServicesValidation;

import static config.EnvGlobals.restServiceID;
import static stepdefs.Hooks.RequestPayLoad;
import static stepdefs.Hooks.endPoint;

public class RestServices {

    @Given("I Set Add a rest service")
    public void iSetAddARestService() {
        endPoint = EndpointURLs.ADD_REST_SERVICE;
        RequestPayLoad = RestServicesPayload.addRestService();
    }

    @Then("I receive a valid Response for adding a rest service")
    public void iReceiveAValidResponseForAddingARestService() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
        restServiceID = ReusableFunctions.getResponsePath("id");
        RestServicesValidation.validateRestServiceResponse();
    }


    @Given("I Set Get a list of all rest services")
    public void iSetGetAListOfAllRestServices() {
        endPoint = EndpointURLs.LIST_REST_SERVICES;
    }

    @Then("I receive a valid Response for Get a list of rest services")
    public void iReceiveAValidResponseForGetAListOfRestServices() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get a specific rest service")
    public void iSetGetASpecificRestService() {
        endPoint = String.format(EndpointURLs.LIST_SPECIFIC_RESTSERVICE + restServiceID);
    }

    @Then("I receive a valid Response for getting a specific rest service")
    public void iReceiveAValidResponseForGettingASpecificRestService() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set Delete a rest service")
    public void iSetDeleteARestService() {
        endPoint = String.format(EndpointURLs.DELETE_A_RESTSERVICE + restServiceID);
    }

    @Then("I receive a valid Response for deleting a rest service")
    public void iReceiveAValidResponseForDeletingARestService() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_NO_CONTENT);

    }

    @Given("I Set Add a google sheet sync")
    public void iSetAddAGoogleSheetSync() {
        endPoint = EndpointURLs.ADD_GOOGLE_SHEET_SYNC;
        RequestPayLoad = RestServicesPayload.addGoogleSheet();
    }

    @Then("I receive a valid Response for adding a google sheet sync")
    public void iReceiveAValidResponseForAddingAGoogleSheetSync() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
    }
}

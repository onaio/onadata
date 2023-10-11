package stepdefs;

import config.EndpointURLs;
import cucumber.api.java.en.And;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;
import payloads.MetadataPayload;
import validation.MetadataValidation;

import static config.EnvGlobals.getFormID;
import static config.EnvGlobals.getMetadataID;
import static stepdefs.Hooks.RequestPayLoad;
import static stepdefs.Hooks.endPoint;

public class Metadata {

    @Given("I Set Create metadata")
    public void iSetCreateMetadata() {
        endPoint = EndpointURLs.CREATE_METADATA;
        RequestPayLoad = MetadataPayload.createMetadata();

    }

    @Then("I receive a valid Response for Create metadata")
    public void iReceiveAValidResponseForCreateMetadata() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
        getMetadataID = ReusableFunctions.getResponsePath("id");
        MetadataValidation.validateMetadataResponse();
    }

    @Given("I Set GET form metadata api endpoint")
    public void i_Set_Get_form_metadata_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_FORM_METADATA + getFormID);
    }

    @Then("I receive valid Response for Get form metadata service")
    public void i_receive_valid_Response_for_Get_form_metadata_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set GET specific metadata api endpoint")
    public void i_Set_Get_specific_metadata_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_SPECIFIC_METADATA + getMetadataID);
    }

    @Then("I receive valid Response for Get specific metadata service")
    public void i_receive_valid_Response_for_Get_specific_metadata_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }


    @And("I Set Delete metadata")
    public void iSetDeleteMetadata() {
        endPoint = String.format(EndpointURLs.DELETE_METADATA + getMetadataID);

    }

    @Then("I receive a valid Response for deleting metadata")
    public void iReceiveAValidResponseForDeletingMetadata() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_NO_CONTENT);
    }
}

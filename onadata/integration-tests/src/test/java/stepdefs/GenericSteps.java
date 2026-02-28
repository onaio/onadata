package stepdefs;

import config.ConfigProperties;
import config.EnvGlobals;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.When;
import general.ReusableFunctions;

import static config.ConfigProperties.password;
import static config.ConfigProperties.username;
import static stepdefs.Hooks.*;

public class GenericSteps {

    @Given("I am Testing Case : {string}")
    public void i_am_Testing_Case(String caseId) {
        Hooks.caseID = caseId;
    }

    @When("I Set request HEADER and PAYLOAD")
    public void i_Set_request_HEADER_and_PAYLOAD() {
        ReusableFunctions.givenHeaderPayload(ReusableFunctions.headers(Hooks.HEADER_AUTHORIZATION, EnvGlobals.apiToken, Hooks.HEADER_AUTHORIZATION,EnvGlobals.apiToken), RequestPayLoad);
    }

    @When("Send a POST HTTP request")
    public void send_a_POST_HTTP_request() {
        ReusableFunctions.whenFunction(Hooks.HTTP_METHOD_POST, ConfigProperties.baseUrl + endPoint);
    }
    @When("I Set request HEADER")
    public void i_Set_request_HEADER() {
        ReusableFunctions.givenHeaders(ReusableFunctions.headers(Hooks.HEADER_AUTHORIZATION, EnvGlobals.apiToken, Hooks.HEADER_AUTHORIZATION,EnvGlobals.apiToken));
    }
    @When("Send a GET HTTP request")
    public void send_a_GET_HTTP_request() {
        ReusableFunctions.whenFunction(Hooks.HTTP_METHOD_GET, ConfigProperties.baseUrl + endPoint);
    }

    @When("Send a PUT HTTP request")
    public void send_a_PUT_HTTP_request() {
        ReusableFunctions.whenFunction(Hooks.HTTP_METHOD_PUT, ConfigProperties.baseUrl + endPoint);
    }

    @When("Send a PATCH HTTP request")
    public void send_a_PATCH_HTTP_request() {
        ReusableFunctions.whenFunction(Hooks.HTTP_METHOD_PATCH,  ConfigProperties.baseUrl + endPoint);
    }

    @When("I Set request HEADER and FORMDATA")
    public void i_Set_request_HEADER_and_FORMDATA() {
        ReusableFunctions.givenHeaderFormData(ReusableFunctions.headers(Hooks.HEADER_AUTHORIZATION, EnvGlobals.apiToken, Hooks.HEADER_AUTHORIZATION,EnvGlobals.apiToken), RequestFormData);
    }

    @When("Send a DELETE HTTP request")
    public void send_a_DELETE_HTTP_request()
    {
        ReusableFunctions.whenFunction(HTTP_METHOD_DELETE, ConfigProperties.baseUrl + endPoint);
    }

    @When("I Set Digest Auth")
    public void i_Set_Digest_Auth() {
        ReusableFunctions.setDigestAuth(username, password);

    }


}

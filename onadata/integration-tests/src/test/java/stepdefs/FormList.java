package stepdefs;

import config.EndpointURLs;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;

import static config.EnvGlobals.getFormID;

import static stepdefs.Hooks.endPoint;

public class FormList {
    @Given("I Set Get list of Forms in account api endpoint")
    public void i_Set_GET_list_of_forms_in_account_api_endpoint() {
        endPoint = EndpointURLs.GET_LIST_OF_FORMS_IN_ACCOUNT;
    }

    @Then("I receive valid Response for Get list of Forms in account")
    public void i_receive_valid_Response_for_Get_list_of_forms_in_account_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get a specific form api endpoint")
    public void i_Set_GET_a_specific_form_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_A_SPECIFIC_FORM.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for Get a specific form")
    public void i_receive_valid_Response_for_Get_a_specific_form_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set filter Forms with enketo api endpoint")
    public void i_Set_filter_forms_with_enketo_api_endpoint() {
        endPoint = String.format(EndpointURLs.FILTER_FORM_WITH_ENKETO.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for filter Forms with enketo")
    public void i_receive_valid_Response_for_filter_forms_with_enketo_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set filter Forms with enketo preview api endpoint")
    public void i_Set_filter_forms_with_enketo_preview_api_endpoint() {
        endPoint = String.format(EndpointURLs.FILTER_FORM_WITH_PREVIEW.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for filter Forms with enketo preview")
    public void i_receive_valid_Response_for_filter_forms_with_enketo_preview_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }
}

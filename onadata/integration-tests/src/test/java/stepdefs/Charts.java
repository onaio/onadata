package stepdefs;

import config.EndpointURLs;
import config.EnvGlobals;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import cucumber.api.java.en.When;
import general.ReusableFunctions;

import static config.EnvGlobals.getFormID;
import static stepdefs.Hooks.endPoint;

public class Charts {
    @Given("I Set Get charts accessible by user api endpoint")
    public void i_Set_GET_charts_accessible_by_user_api_endpoint() {
        endPoint = EndpointURLs.GET_CHARTS_ACCESSIBLE_BY_USER;
    }

    @Then("I receive valid Response for get charts accessible by user api endpoint")
    public void i_receive_valid_Response_for_get_charts_accessible_by_user_api_endpoint() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get chart fields for specific form api endpoint")
    public void i_Set_GET_chart_fields_for_specific_form_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_CHART_FIELDS + getFormID);
    }

    @Then("I receive valid Response for get chart fields for specific form api endpoint")
    public void i_receive_valid_Response_for_get_chart_fields_for_specific_form_api_endpoint() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }


    @Given("I Set Get chart for specific field api endpoint")
    public void i_Set_GET_chart_for_specific_field_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_CHART_FOR_SPECIFIC_FIELD.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for get chart for specific field api endpoint")
    public void i_receive_valid_Response_for_get_chart_for_specific_field_api_endpoint() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get chart data for all fields api endpoint")
    public void i_Set_GET_chart_data_for_all_fields_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_CHART_DATA_FOR_ALL_FIELDS.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for get chart data for all fields api endpoint")
    public void i_receive_valid_Response_for_get_chart_data_for_all_fields_api_endpoint() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get chart field grouped by another field")
    public void i_Set_Get_chart_field_grouped_by_another_field(){
        endPoint = String.format(EndpointURLs.CHART_FIELD_GROUPED_BY_ANOTHER_FIELD.replace("{id}", getFormID));
    }

    @Then("I receive a valid Response for chart field grouped by another field")
    public void i_receive_a_valid_Response_for_chart_field_grouped_by_another_field(){
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }




}

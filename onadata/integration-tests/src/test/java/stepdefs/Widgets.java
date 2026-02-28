package stepdefs;

import config.EndpointURLs;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;


import validation.WidgetsValidation;
import payloads.WidgetsPayload;


import static config.EnvGlobals.*;
import static stepdefs.Hooks.endPoint;
import static stepdefs.Hooks.RequestPayLoad;
import static general.GeneralFunctions.generateAlphaNumeric;

public class Widgets {
    @Given("I Set POST Widget service api endpoint")
    public void i_Set_POST_Widget_service_api_endpoint() {
        endPoint = EndpointURLs.CREATE_WIDGET;
        widgetTitle = generateAlphaNumeric("New widget title", 2);
        RequestPayLoad = WidgetsPayload.createWidgets(widgetTitle, getFormID);
    }

    @Then("I receive valid Response for POST Widget service")
    public void i_receive_valid_Response_for_POST_Widget_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
        getWidgetID = ReusableFunctions.getResponsePath("id");
        getWidgetKey = ReusableFunctions.getResponsePath( "key");
        WidgetsValidation.validateWidgetResponse(widgetTitle);
        getWidgetID = ReusableFunctions.getResponsePath("id");
        getWidgetKey = ReusableFunctions.getResponsePath( "key");
    }

    @Given("I Set Get widget api endpoint")
    public void i_Set_GET_widget_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_A_WIDGET + getWidgetID);
    }

    @Then("I receive valid Response for Get widget api endpoint")
    public void i_receive_valid_Response_for_get_widget_api_endpoint() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get list of Widgets api endpoint")
    public void i_Set_GET_list_of_widgets_api_endpoint() {
        endPoint = EndpointURLs.GET_LIST_OF_WIDGETS;
    }

    @Then("I receive valid Response for Get list of Widgets api endpoint")
    public void i_receive_valid_Response_for_Get_list_of_widgets_api_endpoint() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }


    @Given("I Set PUT update widget service api endpoint")
    public void i_Set_PUT_update_widget_service_api_endpoint() {
        endPoint = String.format(EndpointURLs.UPDATE_A_WIDGET + getWidgetID);
        widgetTitle = generateAlphaNumeric("New Widget Title", 2);
        RequestPayLoad = WidgetsPayload.updateWidgets(widgetTitle, getFormID);
    }

    @Then("I receive valid Response for update widget service")
    public void i_receive_valid_Response_for_update_widget_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set PATCH a widget service api endpoint")
    public void i_Set_PATCH_a_widget_service_api_endpoint() {
        endPoint = String.format(EndpointURLs.PATCH_A_WIDGET + getWidgetID);
        RequestPayLoad = WidgetsPayload.patchWidgets();

    }

    @Then("I receive valid Response for patch a widget service")
    public void i_receive_valid_Response_for_patch_a_widget_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET Widgets data service api endpoint")
    public void i_Set_GET_widgets_data_service_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_WIDGETS_DATA.replace("{id}", getWidgetID));
    }

    @Then("I receive valid Response for Get Widgets data service")
    public void i_receive_valid_Response_for_Get_widgets_data_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET widget with valid key api endpoint")
    public void i_Set_GET_widget_with_valid_key_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_WIDGET_WITH_VALID_kEY + getWidgetKey);
    }

    @Then("I receive valid Response for Get widget with valid key service")
    public void i_receive_valid_Response_for_Get_widget_with_valid_key_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set filter widget by formid api endpoint")
    public void i_Set_filter_widget_with_formid_api_endpoint() {
        endPoint = String.format(EndpointURLs.FILTER_WIDGET_BY_FORMID + getFormID);
    }

    @Then("I receive valid Response for filter widget by formid key service")
    public void i_receive_valid_Response_for_filter_widget_with_formid_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set filter widget by dataset api endpoint")
    public void i_Set_filter_widget_by_dataset_api_endpoint() {
        endPoint = EndpointURLs.FILTER_WIDGET_BY_DATASET;
    }

    @Then("I receive valid Response for filter widget by dataset key service")
    public void i_receive_valid_Response_for_filter_widget_by_dataset_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

}

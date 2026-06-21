package stepdefs;


import config.EndpointURLs;
import config.EnvGlobals;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import cucumber.api.java.en.When;
import formdata.FormsFormData;
import general.ReusableFunctions;

import payloads.FormsPayload;

import static config.EnvGlobals.*;
import static general.GeneralFunctions.generateAlphaNumeric;
import static stepdefs.Hooks.*;

public class Forms {

    @Given("I Set Post import data service api endpoint")
    public void i_Set_GET_Post_import_data_service_api_endpoint() {
        endPoint = String.format(EndpointURLs.IMPORT_DATA_CSV.replace( "{id}", getFormID));
    }

    @Then("I receive valid Response for import data service")
    public void i_receive_valid_Response_for_import_data_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set GET all Data exports api endpoint")
    public void i_Set_GET_all_Data_exports_api_endpoint() {
        endPoint = EndpointURLs.GET_ALL_EXPORTS;
    }

    @Then("I receive valid Response for GET all Data exports")
    public void i_receive_valid_Response_for_GET_all_Data_exports() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET form exports api endpoint")
    public void i_Set_GET_form_exports_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_FORM_EXPORTS + getFormID);
    }

    @Then("I receive valid Response for GET form exports")
    public void i_receive_valid_Response_for_GET_form_exports() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET Data export in csv api endpoint")
    public void i_Set_GET_Data_export_in_csv_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_EXPORT_IN_CSV.replace( "{id}", getFormID));
    }

    @Then("I receive valid Response for GET Data export in csv")
    public void i_receive_valid_Response_for_GET_Data_export_in_csv() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_ACCEPTED);

    }

    @Given("I Set GET Data export in xls api endpoint")
    public void i_Set_GET_Data_export_in_xls_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_EXPORT_IN_XLS.replace( "{id}", getFormID));
    }

    @Then("I receive valid Response for GET Data export in xls")
    public void i_receive_valid_Response_for_GET_Data_export_in_xls() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_ACCEPTED);

    }

    @Given("I Set GET Data export in csvzip api endpoint")
    public void i_Set_GET_data_export_in_csvzip_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_EXPORT_IN_CSVZIP.replace( "{id}", getFormID));
    }

    @Then("I receive valid Response for GET Data export in csvzip")
    public void i_receive_valid_Response_for_GET_export_in_csvzip() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_ACCEPTED);

    }

    @Given("I Set GET Data export in sav api endpoint")
    public void i_Set_GET_Data_export_in_sav_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_EXPORT_IN_SAV.replace( "{id}", getFormID));
    }

    @Then("I receive valid Response for GET Data export in sav")
    public void i_receive_valid_Response_for_GET_Data_export_in_sav() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_ACCEPTED);

    }

    @Given("I Set GET list of Forms api endpoint")
    public void i_Set_GET_list_of_forms_api_endpoint() {
        endPoint = EndpointURLs.GET_LIST_OF_FORMS;
    }

    @Then("I receive valid Response for GET list of Forms service")
    public void i_receive_valid_Response_for_GET_list_of_forms_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET form xml representation api endpoint")
    public void i_Set_GET_form_xml_representation_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_FORM_XML_REPRESENTATION.replace( "{id}", getFormID));
    }

    @Then("I receive valid Response for GET form xml representation service")
    public void i_receive_valid_Response_for_GET_form_xml_representation_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET form json representation api endpoint")
    public void i_Set_GET_form_json_representation_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_FORM_JSON_REPRESENTATION.replace( "{id}", getFormID));
    }

    @Then("I receive valid Response for GET form json representation service")
    public void i_receive_valid_Response_for_GET_form_json_representation_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET xlsform representation api endpoint")
    public void i_Set_GET_xlsform_representation_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_XLSFORM_REPRESENTATION.replace( "{id}", getFormID));
    }

    @Then("I receive valid Response for GET xlsform representation service")
    public void i_receive_valid_Response_for_GET_xlsform_representation_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set add tags to a form api endpoint")
    public void i_Set_add_tags_to_a_form_api_endpoint()
    {
        endPoint = String.format(EndpointURLs.ADD_TAGS_TO_A_FORM.replace( "{id}", getFormID));
        newTag = generateAlphaNumeric( "tag", 4);
        RequestPayLoad = FormsPayload.addTag(newTag);
    }

    @Then("I receive valid Response for add tags to a form")
    public void i_receive_valid_response_for_add_tags_to_a_form(){
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
//        getFormTag = ReusableFunctions.getResponsePath( "labels");
        System.out.println(getFormTag);
    }


    @Given("I Set GET form tags api endpoint")
    public void i_Set_GET_form_tags_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_TAGS.replace( "{id}", getFormID));
    }

    @Then("I receive valid Response for GET form tags service")
    public void i_receive_valid_Response_for_GET_form_tags_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET form with specific tags api endpoint")
    public void i_Set_GET_form_with_specific_tags_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_FORM_WITH_SPECIFIC_TAGS + getFormTag);
    }

    @Then("I receive valid Response for GET form with specific tags service")
    public void i_receive_valid_Response_for_GET_form_with_specific_tags_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET form enketo urls api endpoint")
    public void i_Set_GET_form_enketo_urls_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_ENKETO_URLS.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for GET form enketo urls service")
    public void i_receive_valid_Response_for_GET_form_enketo_urls_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET single submission url api endpoint")
    public void i_Set_GET_single_submission_url_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_SINGLE_SUBMISSION_URL.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for GET single submission url service")
    public void i_receive_valid_Response_for_GET_single_submission_url_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET form csv data api endpoint")
    public void i_Set_GET_form_csv_data_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_FORM_CSV_DATA.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for GET form csv data service")
    public void i_receive_valid_Response_for_GET_form_csv_data_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET form xls data api endpoint")
    public void i_Set_GET_form_xls_data_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_FORM_XLS_DATA.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for GET form xls data service")
    public void i_receive_valid_Response_for_GET_form_xls_data_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET form versions api endpoint")
    public void i_Set_GET_form_versions_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_FORM_VERSIONS.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for GET form versions service")
    public void i_receive_valid_Response_for_GET_form_versions_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set filter forms by owner")
    public void i_set_filter_forms_by_owner(){
        endPoint = EndpointURLs.FILTER_FORMS_BY_OWNER;
    }

    @Then("I receive a valid Response for filtering forms by owner")
    public void i_receive_a_valid_Response_for_filtering_forms_by_owner(){
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set paginate list of forms")
    public void i_Set_paginate_list_of_forms(){
        endPoint = EndpointURLs.PAGINATE_LIST_OF_FORMS;
    }

    @Then("I receive a valid Response for paginating list of forms")
    public void i_receive_a_valid_Response_for_paginating_list_of_forms(){
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get form information")
    public void i_Set_Get_form_information(){
        endPoint = String.format(EndpointURLs.GET_FORM_INFORMATION + getFormID);
    }

    @Then("I receive a valid Response for getting form information")
    public void i_receive_a_valid_Response_for_getting_form_information(){
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set replace form api endpoint")
    public void i_Set_replace_form_api_endpoint(){
        endPoint = String.format(EndpointURLs.REPLACE_A_FORM + getFormID);
        RequestFormData = FormsFormData.replaceForm();
    }

    @Then("I receive a valid Response for replacing a form")
    public void i_receive_a_valid_Response_for_replacing_a_form(){
        ReusableFunctions.thenFunction(HTTP_RESPONSE_SUCCESS);
    }

    @When("I Set formreplacement request HEADER")
    public void i_Set_formreplacement_request_HEADER() {
        ReusableFunctions.givenHeaderFormData(ReusableFunctions.headers(Hooks.HEADER_AUTHORIZATION, EnvGlobals.apiToken, Hooks.HEADER_AUTHORIZATION,EnvGlobals.apiToken));
        ReusableFunctions.addFileInHeader("Colourful_Choices.xlsx","xls_file","application/vnd.ms-excel");

    }

    @Given("I Set clone a form api endpoint")
    public void i_Set_clone_a_form_api_endpoint(){
        endPoint = String.format(EndpointURLs.CLONE_A_FORM.replace("{id}", getFormID));
        RequestFormData = FormsFormData.cloneForm();
    }

    @Then("I receive a valid Response for cloning a form")
    public void i_receive_a_valid_Response_for_cloning_a_form(){
        ReusableFunctions.thenFunction(HTTP_RESPONSE_CREATED);
        cloneFormID = ReusableFunctions.getResponsePath("formid");
    }

    @Given("I Set Delete cloned form")
    public void i_Set_Delete_cloned_form(){
        endPoint = String.format(EndpointURLs.DELETE_CLONED_FORM + cloneFormID);
    }

    @Then("I receive a valid Response for deleting cloned form")
    public void i_receive_a_valid_Response_for_deleting_cloned_form(){
        ReusableFunctions.thenFunction(HTTP_RESPONSE_NO_CONTENT);
    }

}

package stepdefs;

import config.EndpointURLs;
import config.EnvGlobals;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import cucumber.api.java.en.When;
import general.ReusableFunctions;



import validation.MergedDatasetsValidation;
import payloads.MergedDatasetPayload;


import static config.EnvGlobals.*;

import static general.GeneralFunctions.generateAlphaNumeric;
import static stepdefs.Hooks.*;

public class MergedDatasets {

    @Given("I Set upload another test form")
    public void i_set_upload_another_test_form(){
        endPoint = String.format(EndpointURLs.UPLOAD_A_FORM.replace("{id}", getProjectID));

    }

    @Then("I receive a valid Response for uploading a test form")
    public void i_receive_valid_response_for_uploading_a_test_form() {
        ReusableFunctions.thenFunction(HTTP_RESPONSE_CREATED);
        getFormID2 = ReusableFunctions.getResponsePath("formid");
        System.out.println(getFormID2);

    }

    @When("I Set formupload2 request HEADER")
    public void i_Set_formupload2_request_HEADER() {
        ReusableFunctions.givenHeaderFormData(ReusableFunctions.headers(Hooks.HEADER_AUTHORIZATION, EnvGlobals.apiToken, Hooks.HEADER_AUTHORIZATION, EnvGlobals.apiToken));
        ReusableFunctions.addFileInHeader("Colourful_Choices2.xlsx", "xls_file", "application/vnd.ms-excel");
    }

    @Given("I Set import data service api endpoint")
    public void i_Set_import_data_service_api_endpoint() {
        endPoint = String.format(EndpointURLs.IMPORT_DATA_CSV.replace( "{id}", getFormID2));
    }

    @Then("I receive valid Response for importing data service")
    public void i_receive_valid_Response_for_importing_data_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set POST merge datasets api endpoint")
    public void i_Set_Post_merge_datasets_api_endpoint() {
        endPoint = EndpointURLs.MERGE_DATASETS;
        datasetTitle = generateAlphaNumeric("NewDataset", 3);
        RequestPayLoad = MergedDatasetPayload.mergeDatasets(datasetTitle);
    }

    @Then("I receive valid Response for merge datasets service")
    public void i_receive_valid_Response_for_merge_datasets_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
        mergedDatasetID = ReusableFunctions.getResponsePath( "id");
        System.out.println(mergedDatasetID);
        MergedDatasetsValidation.validateMergedResponse(datasetTitle);
        mergedDatasetID = ReusableFunctions.getResponsePath( "id");
        System.out.println(mergedDatasetID);
    }

    @Given("I Set GET merged dataset api endpoint")
    public void i_Set_Get_merged_dataset_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_MERGED_DATASET + mergedDatasetID);
    }

    @Then("I receive valid Response for Get merged dataset service")
    public void i_receive_valid_Response_for_Get_merged_dataset_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set GET all merged datasets api endpoint")
    public void i_Set_Get_all_merged_datasets_api_endpoint() {
        endPoint = EndpointURLs.GET_ALL_MERGED_DATASETS;
    }

    @Then("I receive valid Response for Get all merged datasets service")
    public void i_receive_valid_Response_for_Get_all_merged_datasets_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set GET data in merged datasets api endpoint")
    public void i_Set_Get_data_in_merged_datasets_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_IN_MERGED_DATASET.replace("{id}", mergedDatasetID));
    }

    @Then("I receive valid Response for Get data in merged datasets service")
    public void i_receive_valid_Response_for_Get_data_in_merged_datasets_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Delete a merged dataset")
    public void i_Set_Delete_a_merged_dataset(){
        endPoint = String.format(EndpointURLs.DELETE_A_MERGED_DATASET + mergedDatasetID);

    }

    @Then("I receive a valid Response for deleting a merged dataset")
    public void i_receive_a_valid_Response_for_deleting_a_merged_dataset(){
        ReusableFunctions.thenFunction(HTTP_RESPONSE_NO_CONTENT);

    }



}

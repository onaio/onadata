package stepdefs;

import config.EndpointURLs;
import config.EnvGlobals;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;


import payloads.FilteredDatasetsPayload;

import validation.FilteredDatasetsValidation;

import static config.EnvGlobals.filteredDatasetID;
import static stepdefs.Hooks.RequestPayLoad;
import static stepdefs.Hooks.endPoint;
import static config.EnvGlobals.datasetName;
import static general.GeneralFunctions.generateAlphaNumeric;



public class FilteredDatasets {
    @Given("I Set POST filtered dataset api endpoint")
    public void i_Set_Post_filtered_dataset_api_endpoint() {
        endPoint = EndpointURLs.CREATE_FILTERED_DATASET;
        datasetName = generateAlphaNumeric("dataview", 2);
        RequestPayLoad = FilteredDatasetsPayload.createDataset(datasetName);
    }

    @Then("I receive valid Response for create filtered datasets service")
    public void i_receive_valid_Response_for_create_filtered_datasets_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
        filteredDatasetID = ReusableFunctions.getResponsePath("dataviewid");
        FilteredDatasetsValidation.validateDatasetResponse(datasetName);
        filteredDatasetID = ReusableFunctions.getResponsePath("dataviewid");
    }

    @Given("I Set GET filtered dataset api endpoint")
    public void i_Set_Get_filtered_dataset_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_FILTERED_DATASET + filteredDatasetID);
    }

    @Then("I receive valid Response for Get filtered dataset service")
    public void i_receive_valid_Response_for_Get_filtered_dataset_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set update filtered dataset api endpoint")
    public void i_Set_update_filtered_dataset_api_endpoint() {
        endPoint = String.format(EndpointURLs.UPDATE_A_DATASET + filteredDatasetID);
        datasetName = generateAlphaNumeric("dataview", 2);
        RequestPayLoad = FilteredDatasetsPayload.updateDataset(datasetName);
    }

    @Then("I receive valid Response for update filtered dataset service")
    public void i_receive_valid_Response_for_update_filtered_dataset_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        FilteredDatasetsValidation.validateDatasetResponse(datasetName);
    }

    @Given("I Set Patch filtered dataset api endpoint")
    public void i_Set_Patch_filtered_dataset_api_endpoint() {
        endPoint = String.format(EndpointURLs.PATCH_A_DATASET + filteredDatasetID);
        datasetName = generateAlphaNumeric("dataview", 2);
        RequestPayLoad = FilteredDatasetsPayload.patchDataset(datasetName);
    }

    @Then("I receive valid Response for patch filtered dataset service")
    public void i_receive_valid_Response_for_patch_filtered_dataset_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        FilteredDatasetsValidation.validateDatasetResponse(datasetName);
    }

    @Given("I Set GET data from filtered dataset api endpoint")
    public void i_Set_Get_data_from_filtered_dataset_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_FROM_A_DATASET.replace("{id}", filteredDatasetID));
    }

    @Then("I receive valid Response for Get data from filtered dataset service")
    public void i_receive_valid_Response_for_Get_data_from_filtered_dataset_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set GET filtered data using limit operators")
    public void i_Set_Get_filtered_data_using_limit_operators() {
        endPoint = String.format(EndpointURLs.GET_DATA_USING_LIMIT_OPERATORS.replace("{id}", filteredDatasetID));
    }

    @Then("I receive valid Response for Get filtered data using limit operators")
    public void i_receive_valid_Response_for_Get_filtered_data_using_limit_operators() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set GET filtered data using start limit operators")
    public void i_Set_Get_filtered_data_using_start_limit_operators() {
        endPoint = String.format(EndpointURLs.GET_DATA_USING_START_LIMIT_OPERATORS.replace("{id}", filteredDatasetID));
    }

    @Then("I receive valid Response for Get filtered data using start limit operators")
    public void i_receive_valid_Response_for_Get_filtered_data_using_start_limit_operators() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set count data in filtered dataset api endpoint")
    public void i_Set_count_data_in_filtered_dataset_api_endpoint() {
        endPoint = String.format(EndpointURLs.COUNT_DATA_IN_DATASET.replace("{id}", filteredDatasetID));
    }

    @Then("I receive valid Response for count data in filtered dataset")
    public void i_receive_valid_Response_for_count_data_in_filtered_dataset() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set export data in dataset api endpoint")
    public void i_Set_export_data_in_dataset_api_endpoint() {
        endPoint = String.format(EndpointURLs.EXPORT_DATA_IN_DATASET.replace("{id}", filteredDatasetID));
    }

    @Then("I receive valid Response for export data in dataset")
    public void i_receive_valid_Response_for_export_data_in_dataset() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_ACCEPTED);
    }

    @Given("I Set Get charts in dataset api endpoint")
    public void i_Set_Get_charts_in_dataset_api_endpoint() {
        endPoint = String.format(EndpointURLs.CHARTS_IN_DATASET.replace("{id}", filteredDatasetID));
    }

    @Then("I receive valid Response for Get charts in dataset")
    public void i_receive_valid_Response_for_Get_charts_in_dataset() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get chart field in dataset api endpoint")
    public void i_Set_Get_chart_field_in_dataset_api_endpoint() {
        endPoint = String.format(EndpointURLs.CHART_FOR_SPECIFIC_FIELD.replace("{id}", filteredDatasetID));
    }

    @Then("I receive valid Response for Get chart field in dataset")
    public void i_receive_valid_Response_for_Get_chart_field_in_dataset() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Delete a filtered dataset")
    public void i_Set_Delete_a_filtered_dataset(){
        endPoint = String.format(EndpointURLs.DELETE_A_FILTERED_DATASET + filteredDatasetID);
    }

    @Then("I receive a valid Response for deleting a filtered dataset")
    public void i_receive_a_valid_Response_for_deleting_a_filtered_dataset(){
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_NO_CONTENT);
    }
}

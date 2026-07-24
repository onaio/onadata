package stepdefs;

import config.EndpointURLs;
import config.EnvGlobals;
import cucumber.api.java.en.And;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import cucumber.api.java.en.When;
import general.ReusableFunctions;
import org.json.JSONArray;

import static config.EnvGlobals.*;
import static config.EnvGlobals.fileName;
import static stepdefs.Hooks.endPoint;

public class DataSteps {

    @Given("I Set GET Data service api endpoint")
    public void i_Set_GET_Data_service_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA + getFormID);
    }
    @Then("I receive valid Response for GET Data service")
    public void i_receive_valid_Response_for_GET_Data_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        JSONArray getMediaKey2 = ReusableFunctions.getResponseJson( "_id", "_xform_id");

        instance = String.valueOf(getMediaKey2.getJSONObject(0).getInt("_id"));

        System.out.println(instance);
    }

    @When("I Set csvmultipart request HEADER")
    public void i_Set_csvmultipart_request_HEADER() {
        ReusableFunctions.givenHeaderFormData(ReusableFunctions.headers(Hooks.HEADER_AUTHORIZATION, EnvGlobals.apiToken, Hooks.HEADER_AUTHORIZATION,EnvGlobals.apiToken));
        ReusableFunctions.addFileInHeader("Colourful_Choices_1.csv","csv_file","text/csv");

    }

    @Given("I Set GET Data service using start value api endpoint")
    public void i_Set_GET_Data_service_using_start_value_api_endpoint() {
       endPoint = String.format(EndpointURLs.GET_DATA_USING_START_VALUE.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for GET Data  using start value service")
    public void i_receive_valid_Response_for_GET_Data_using_start_value_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }
    @Given("I Set GET Data on select columns for a given form api endpoint")
    public void i_Set_GET_Data_on_select_columns_for_a_given_form_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_BY_COLUMN.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET Data on select columns for a given form")
    public void i_receive_valid_Response_for_GET_Data_on_select_columns_for_a_given_form() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET Data service using start and limit values api endpoint")
    public void i_Set_GET_Data_service_using_start_and_limit_values_api_endpoint() {
      endPoint = String.format(EndpointURLs.GET_DATA_USING_START_LIMIT.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for GET Data  using start and limit values service")
    public void i_receive_valid_Response_for_GET_Data_using_start_and_limit_values_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }
    @Given("I Set GET Data service for all Forms in CSV format api endpoint")
    public void i_Set_GET_Data_service_for_all_forms_in_CSV_format_api_endpoint() {
            endPoint = EndpointURLs.GET_ALL_DATA_CSV_FORMAT;
        }

    @Then("I receive valid Response for GET Data for all Forms in CSV formate service")
    public void i_receive_valid_Response_for_GET_Data_for_all_forms_in_CSV_formate_service() {
            ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

        }

    @Given("I Set GET Data service for specific form in CSV format api endpoint")
    public void i_Set_GET_Data_service_for_specific_form_in_CSV_format_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_CSV_FORMAT.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET Data for specific form in CSV format service")
    public void i_receive_valid_Response_for_GET_Data_for_specific_form_in_CSV_format_service() {
            ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

        }

    @Given("I Set GET Data service filter by owner api endpoint")
    public void i_Set_GET_Data_service_filter_by_owner_api_endpoint() {
        endPoint = EndpointURLs.FILTER_DATA_BY_OWNER;

    }

    @Then("I receive valid Response for GET Data filter by owner service")
    public void i_receive_valid_Response_for_GET_Data_filter_by_owner_service() {
            ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

        }

    @Given("I Set GET JSON list of submitted data for a specific form api endpoint")
    public void i_Set_GET_JSON_list_of_submitted_data_for_a_specific_form_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_JSON_DATA_SPECIFIC_FORM + getFormID);

    }

    @Then("I receive valid Response for JSON list of submitted data for a specific form service")
    public void i_receive_valid_Response_for_JSON_list_of_submitted_data_for_a_specific_form_service() {
            ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

        }

    @Given("I Set GET XML list of submitted data for a specific form api endpoint")
    public void i_Set_GET_XML_list_of_submitted_data_for_a_specific_form_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_XML_DATA_SPECIFIC_FORM.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET XML list of submitted data for a specific form service")
    public void i_receive_valid_Response_for_GET_XML_list_of_submitted_data_for_a_specific_form_service() {
            ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

        }

    @Given("I Set GET Paginate data of a specific form api endpoint")
    public void i_Set_GET_Paginate_data_of_a_specific_form_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_BY_PAGINATION.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET Paginate data of a specific form service")
    public void i_receive_valid_Response_for_GET_Paginate_data_of_a_specific_form_service() {
            ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

        }


    @Given("I Set GET Sort submitted data of a specific form in ascending order api endpoint")
    public void i_Set_GET_Sort_submitted_data_of_a_specific_form_in_ascending_order_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_SORT_DATA_ASC_ORDER.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET Sort submitted data of a specific form in ascending order service")
    public void i_receive_valid_Response_for_GET_Sort_submitted_data_of_a_specific_form_in_ascending_order_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET ort submitted data of a specific form in descending order api endpoint")
    public void i_Set_GET_ort_submitted_data_of_a_specific_form_in_descending_order_api_endpoint() {
        String.format(endPoint = EndpointURLs.GET_SORT_DATA_DESC_ORDER.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET Sort submitted data of a specific form in descending order service")
    public void i_receive_valid_Response_for_GET_Sort_submitted_data_of_a_specific_form_in_descending_order_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET a single data submission for a given form api endpoint")
    public void i_Set_GET_a_single_data_submission_for_a_given_form_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_SINGLE_DATA_SUBMISSION_FOR_FORM.replace("{id}", getFormID) + instance);

    }

    @Then("I receive valid Response for GET Paginate a single data submission for a given form service")
    public void i_receive_valid_Response_for_GET_Paginate_a_single_data_submission_for_a_given_form_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }


    @Given("I Set GET Data history of edits made to a submission api endpoint")
    public void i_Set_GET_Data_history_of_edits_made_to_a_submission_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_HISTORY.replace("{id}", "{id2}"), getFormID, instance);
    }


        @Then("I receive valid Response for GET history of edits made to a submission service")
    public void i_receive_valid_Response_for_GET_history_of_edits_made_to_a_submission_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET Data of a specific form using date_created api endpoint")
    public void i_Set_GET_Data_of_a_specific_form_using_date_created_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_BY_CREATED_DATE.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET of a specific form using date_created service")
    public void i_receive_valid_Response_for_GET_of_a_specific_form_using_date_created_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET Data of a specific form using date_modified api endpoint")
    public void i_Set_GET_Data_of_a_specific_form_using_date_modified_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_BY_MODIFIED_DATE.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET Data of a specific form using date_modified service")
    public void i_receive_valid_Response_for_GET_Data_of_a_specific_form_using_date_modified_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET Data of a specific form using last_edited api endpoint")
    public void i_Set_GET_Data_of_a_specific_form_using_last_edited_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_BY_LAST_EDIT_DATE.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET Data of a specific form using last_edited service")
    public void i_receive_valid_Response_for_GET_Data_of_a_specific_form_using_last_edited_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET list of public data api endpoint")
    public void i_Set_GET_list_of_public_data_api_endpoint() {
        endPoint = EndpointURLs.GET_PUBLIC_DATA;

    }

    @Then("I receive valid Response for GET list of public data service")
    public void i_receive_valid_Response_for_GET_list_of_public_data_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET valid geo json value from the submissions api endpoint")
    public void i_Set_GET_valid_geo_json_value_from_the_submissions_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_GEO_JSON_DATA.replace("{id}", "{id2}"), getFormID, instance);

    }

    @Then("I receive valid Response for GET valid geo json value from the submissions service")
    public void i_receive_valid_Response_for_GET_valid_geo_json_value_from_the_submissions_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET Query submissions with APPROVED submission review status api endpoint")
    public void i_Set_GET_Query_submissions_with_APPROVED_submission_review_status_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_BY_APPROVED_STATUS.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET Query submissions with APPROVED submission review status service")
    public void i_receive_valid_Response_for_GET_Query_submissions_with_APPROVED_submission_review_status_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET query submissions with REJECTED submission review status api endpoint")
    public void i_Set_GET_query_submissions_with_REJECTED_submission_review_status_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_BY_REJECTED_STATUS.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET query submissions with REJECTED submission review status service")
    public void i_receive_valid_Response_for_GET_query_submissions_with_REJECTED_submission_review_status_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET Query submissions with PENDING submission review status api endpoint")
    public void i_Set_GET_Query_submissions_with_PENDING_submission_review_status_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_BY_PENDING_STATUS.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET Query submissions with PENDING submission review status service")
    public void i_receive_valid_Response_for_GET_Query_submissions_with_PENDING_submission_review_status_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET Query submissions with pending submission review status or NULL api endpoint")
    public void i_Set_GET_Query_submissions_with_pending_submission_review_status_or_NULL_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_DATA_BY_NULL_STATUS.replace("{id}", getFormID));

    }

    @Then("I receive valid Response for GET Query submissions with pending submission review status or NULL service")
    public void i_receive_valid_Response_for_GET_Query_submissions_with_pending_submission_review_status_or_NULL_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set GET Query submissions with NULL submission review status api endpoint")
    public void i_Set_GET_Query_submissions_with_NULL_submission_review_status_api_endpoint() {
        endPoint = EndpointURLs.GET_DATA_BY_NULL_SUBMISSION_REVIEW;

    }

    @Then("I receive valid Response for GET Query submissions with NULL submission review status service")
    public void i_receive_valid_Response_for_GET_Query_submissions_with_NULL_submission_review_status_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set filter data by owner")
    public void iSetFilterDataByOwner() {

    }

    @Then("I receive a valid Response for filter data by owner")
    public void iReceiveAValidResponseForFilterDataByOwner() {
    }
}

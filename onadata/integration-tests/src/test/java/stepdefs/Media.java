package stepdefs;

import config.EndpointURLs;
import config.EnvGlobals;

import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import cucumber.api.java.en.When;
import general.ReusableFunctions;
import org.json.JSONArray;


import static config.EnvGlobals.*;
import static stepdefs.Hooks.*;

public class Media {

    @Given("I Set upload a test form")
    public void iSetUploadATestForm() {
        endPoint = String.format(EndpointURLs.UPLOAD_A_FORM.replace("{id}", getProjectID));
    }

    @When("I Set testform request HEADER")
    public void iSetTestformRequestHEADER() {
        ReusableFunctions.givenHeaderFormData(ReusableFunctions.headers(Hooks.HEADER_AUTHORIZATION, EnvGlobals.apiToken, Hooks.HEADER_AUTHORIZATION,EnvGlobals.apiToken));
        ReusableFunctions.addFileInHeader("images2.xlsx","xls_file","application/vnd.ms-excel");

    }

    @Then("I receive a valid Response for uploading test form")
    public void iReceiveAValidResponseForUploadingTestForm() {
        ReusableFunctions.thenFunction(HTTP_RESPONSE_CREATED);
        getFormID = ReusableFunctions.getResponsePath( "formid");
        System.out.println(getFormID);
    }

    @Given("I Set Post XML submission")
    public void iSetPostXMLSubmission() {
        endPoint = EndpointURLs.UPLOAD_XML_SUBMISSION;

    }

    @When("I Set XMLSubmission request HEADER")
    public void iSetXMLSubmissionRequestHEADER() {
        ReusableFunctions.givenHeaderFormData(ReusableFunctions.headers(Hooks.HEADER_AUTHORIZATION, EnvGlobals.apiToken, Hooks.HEADER_AUTHORIZATION,EnvGlobals.apiToken));
        ReusableFunctions.addFileInHeader("images.xml","xml_submission_file","text/xml");
        ReusableFunctions.addFileInHeader("photo-02.jpeg","image","image/jpeg");

    }

    @Then("I receive a valid Response for posting xml submission")
    public void iReceiveAValidResponseForPostingXmlSubmission() {
        ReusableFunctions.thenFunction(HTTP_RESPONSE_CREATED);
    }

    @Given("I Set Get media files in a form api endpoint")
    public void i_Set_GET_media_files_in_form_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_MEDIA_FILES_IN_FORM + getFormID);
    }

    @Then("I receive valid Response for Get media files in a form service")
    public void i_receive_valid_Response_for_get_media_files_in_form_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        JSONArray getMediaKey1 = ReusableFunctions.getResponseJson("id", "filename");
        JSONArray getMediaKey2 = ReusableFunctions.getResponseJson( "instance", "id");

        mediaID = String.valueOf(getMediaKey1.getJSONObject(0).getInt("id"));
        instance = String.valueOf(getMediaKey2.getJSONObject(0).getInt("instance"));
        fileName = getMediaKey1.getJSONObject(0).getString("filename");

        System.out.println(mediaID);
        System.out.println(instance);
        System.out.println(fileName);
    }

    @Given("I Set paginate media files api endpoint")
    public void i_Set_paginate_media_files_api_endpoint() {
        endPoint = String.format(EndpointURLs.PAGINATE_MEDIA_FILES.replace("{id}", getFormID));
    }

    @Then("I receive valid Response for paginate media files service")
    public void i_receive_valid_Response_for_paginate_media_files_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get details of an attachment api endpoint with mediaid {string}")
    public void i_Set_Get_details_of_an_attachment_api_endpoint_with_mediaid(String string) {
        endPoint = String.format(EndpointURLs.GET_ATTACHMENT_DETAILS + mediaID);
    }


    @Then("I receive valid Response for Get details of an attachment")
    public void i_receive_valid_Response_for_Get_details_of_an_attachment()
    { ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);}



    @Given("I Set Get a specific media file api endpoint {string}")
    public void i_Set_Get_a_specific_media_file_api_endpoint(String string){
            endPoint = String.format(EndpointURLs.GET_SPECIFC_MEDIA_FILE.replace("{id}", mediaID));
        }



    @Then("I receive valid Response for Get a specific media file")
    public void i_receive_valid_Response_for_Get_a_specific_media_file()
    {ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);}


    @Given("I Set Get media file of a specific instance api endpoint {string}")
    public void i_Set_Get_media_file_of_a_specific_instance_api_endpoint(String string)

    {
        endPoint = String.format(EndpointURLs.GET_MEDIA_OF_SPECIFIC_INSTANCE + instance) ;
    }

    @Then("I receive valid Response for Get media of a specific instance")
    public void i_receive_valid_Response_for_Get_media_of_a_specific_instance()
    { ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);}

    @Given("I Set Filter media files by type api endpoint")
    public void i_Set_Filter_media_files_by_type_api_endpoint()
    { endPoint = EndpointURLs.FILTER_MEDIA_BY_TYPE; }

    @Then("I receive valid Response for filter media by type")
    public void i_receive_valid_Response_for_filter_media_by_type()
    { ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);}

    @Given("I Set Get image link of attachment api endpoint {string} {string}")
    public void i_Set_Get_image_link_of_attachment_api_endpoint(String string, String string1)
    {
        endPoint = String.format(EndpointURLs.GET_IMAGE_LINK_OF_ATTACHMENT.replace("{id}", mediaID) + fileName);
    }

    @Then("I receive valid Response for Get image link of attachment")
    public void i_receive_valid_Response_for_Get_image_link_of_attachment()
    { ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);}



    @Given("I Set Get form media count api endpoint")
    public void i_Set_GET_form_media_count_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_FORM_MEDIA_COUNT + getFormID);
    }

    @Then("I receive valid Response for Get form media count service")
    public void i_receive_valid_Response_for_get_form_media_count_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }


}

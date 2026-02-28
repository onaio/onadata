package stepdefs;

import config.EndpointURLs;
import config.EnvGlobals;

import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import cucumber.api.java.en.When;
import formdata.ProjectFormData;
import general.ReusableFunctions;
import payloads.ProjectsPayload;

import payloads.ProjectsPayload;

import static config.EnvGlobals.*;
import static general.GeneralFunctions.generateAlphaNumeric;
import static stepdefs.Hooks.*;


public class Projects {
    @Given("I Set Create a new project")
    public void i_Set_Create_a_new_project()
    {
        endPoint = EndpointURLs.CREATE_A_PROJECT;
        projectName = generateAlphaNumeric( "API Tests", 4);
        RequestPayLoad = ProjectsPayload.createProject(projectName);
    }

    @Then("I receive a valid Response for Create new project")
    public void i_receive_valid_Response_for_Create_new_project()
    {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
        getProjectID = ReusableFunctions.getResponsePath( "projectid");
        System.out.println(getProjectID);
    }

    @Given("I Set Get list of projects api endpoint")
    public void i_Set_GET_list_of_projects_api_endpoint() {
        endPoint = EndpointURLs.GET_LIST_OF_PROJECTS;
    }

    @Then("I receive valid Response for Get list of projects")
    public void i_receive_valid_Response_for_Get_list_of_projects_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get list of projects by owner api endpoint")
    public void i_Set_GET_list_of_projects_by_owner_api_endpoint() {
        endPoint = EndpointURLs.GET_PROJECTS_BY_OWNER;
    }

    @Then("I receive valid Response for Get list of projects by owner")
    public void i_receive_valid_Response_for_Get_list_of_projects_by_owner_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get project information api endpoint")
    public void i_Set_GET_project_information_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_PROJECT_INFORMATION + getProjectID);
    }

    @Then("I receive valid Response for Get project information")
    public void i_receive_valid_Response_for_Get_project_information_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set update a project api endpoint")
    public void i_Set_update_a_project_api_endpoint() {
        endPoint = String.format(EndpointURLs.UPDATE_A_PROJECT + getProjectID);
        projectName = generateAlphaNumeric( "API Update", 3);
        location = generateAlphaNumeric( "Kilimani", 3);
        RequestPayLoad = ProjectsPayload.updateProject(projectName);
        RequestPayLoad = ProjectsPayload.updateProject(location);

    }

    @Then("I receive valid Response for update a project")
    public void i_receive_valid_Response_for_update_a_project_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set share a project api endpoint")
    public void i_Set_share_a_project_api_endpoint() {
        endPoint = String.format(EndpointURLs.SHARE_A_PROJECT.replace("{id}", getProjectID));
        RequestFormData = ProjectFormData.shareProject();

    }


    @Then("I receive valid Response for share a project")
    public void i_receive_valid_Response_for_share_a_project_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_NO_CONTENT);
    }

    @Given("I Set share a project with multiple users api endpoint")
    public void i_Set_share_project_with_multiple_users_api_endpoint() {
        endPoint = String.format(EndpointURLs.SHARE_MULTIPLE_USERS.replace( "{id}", getProjectID));
        RequestFormData = ProjectFormData.shareMultiple();
    }

    @Then("I receive valid Response for share a project with multiple users")
    public void i_receive_valid_Response_for_share_project_with_multiple_users_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_NO_CONTENT);

    }

    @Given("I send email on sharing a project")
    public void i_send_email_on_sharing_a_project(){
        endPoint = String.format(EndpointURLs.SEND_EMAIL_ON_SHARING.replace( "{id}", getProjectID));
        RequestFormData = ProjectFormData.sendEmail();

    }

    @Then("I receive a valid Response for send email")
    public void i_receive_valid_Response_for_send_email(){
        ReusableFunctions.thenFunction(HTTP_RESPONSE_NO_CONTENT);
    }

    @Given("I Set remove a user api endpoint")
    public void i_Set_remove_a_user_api_endpoint() {
        endPoint = String.format(EndpointURLs.REMOVE_A_USER.replace( "{id}", getProjectID));
        RequestFormData = ProjectFormData.removeUser();
    }

    @Then("I receive valid Response for remove a user")
    public void i_receive_valid_Response_for_remove_a_user_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_NO_CONTENT);
    }

    @Given("I Set assign a form api endpoint")
    public void i_Set_assign_a_form_api_endpoint() {
        endPoint = String.format(EndpointURLs.ASSIGN_A_FORM.replace( "{id}", getProjectID));
        RequestPayLoad = ProjectsPayload.assignForm();
    }

    @Then("I receive valid Response for assign a form")
    public void i_receive_valid_Response_for_assign_a_form_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
    }

    @Given("I Set Get Forms in a project api endpoint")
    public void i_Set_Get_forms_in_a_project_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_FORMS_IN_PROJECT.replace( "{id}", getProjectID));
    }

    @Then("I receive valid Response for Get Forms in a project")
    public void i_receive_valid_Response_for_Get_forms_in_a_project_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set tag a project api endpoint")
    public void i_Set_tag_a_project_api_endpoint() {
        endPoint = String.format(EndpointURLs.TAG_A_PROJECT.replace( "{id}", getProjectID));
        tag = generateAlphaNumeric( "new tag", 1);
        RequestPayLoad = ProjectsPayload.tagProject(tag);
    }

    @Then("I receive valid Response for tag a project")
    public void i_receive_valid_Response_for_tag_a_project_service() {
        getProjectTag = ReusableFunctions.getResponsePath( "tags");
        System.out.println(getProjectTag);
        ReusableFunctions.thenFunction(HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get project tags api endpoint")
    public void i_Set_Get_project_tags_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_PROJECT_TAGS.replace( "{id}", getProjectID));
    }

    @Then("I receive valid Response for Get project tags")
    public void i_receive_valid_Response_for_Get_project_tags() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set filter project by tags api endpoint")
    public void i_Set_filter_project_by_tags_api_endpoint() {
        endPoint = String.format(EndpointURLs.FILTER_PROJECT_BY_TAGS + getProjectTag);
    }

    @Then("I receive valid Response for filter project by tags")
    public void i_receive_valid_Response_for_filter_project_by_tags_service() {
        getProjectTag = ReusableFunctions.getResponsePath( "tag");
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set star a project api endpoint")
    public void i_Set_star_a_project_api_endpoint() {
        endPoint = String.format(EndpointURLs.STAR_A_PROJECT.replace( "{id}", getProjectID));
    }

    @Then("I receive valid Response for star a project")
    public void i_receive_valid_Response_for_star_a_project() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_NO_CONTENT);
    }

    @Given("I Set remove a star api endpoint")
    public void i_Set_remove_a_star_api_endpoint() {
        endPoint = String.format(EndpointURLs.REMOVE_A_STAR.replace( "{id}", getProjectID));
    }

    @Then("I receive valid Response for remove a star")
    public void i_receive_valid_Response_for_remove_a_star_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_NO_CONTENT);
    }

    @Given("I Set Get starred projects api endpoint")
    public void i_Set_Get_starred_projects_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_STARRED_PROJECTS.replace( "{id}", getProjectID));
    }

    @Then("I receive valid Response for Get starred projects")
    public void i_receive_valid_Response_for_Get_starred_projects_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set upload a form to the project")
    public void i_set_upload_a_form_to_project(){
        endPoint = String.format(EndpointURLs.UPLOAD_A_FORM.replace("{id}", getProjectID));
    }

    @Then("I receive a valid Response for uploading a form")
    public void i_receive_valid_response_for_uploading_a_form(){
        ReusableFunctions.thenFunction(HTTP_RESPONSE_CREATED);
        getFormID = ReusableFunctions.getResponsePath( "formid");
        System.out.println(getFormID);

    }

    @When("I Set formupload request HEADER")
    public void i_Set_formupload_request_HEADER() {
        ReusableFunctions.givenHeaderFormData(ReusableFunctions.headers(Hooks.HEADER_AUTHORIZATION, EnvGlobals.apiToken, Hooks.HEADER_AUTHORIZATION,EnvGlobals.apiToken));
        ReusableFunctions.addFileInHeader("Colourful_Choices.xlsx","xls_file","application/vnd.ms-excel");

    }


    @Given("I Set Delete project api endpoint")
    public void i_Set_Delete_project_api_endpoint()
    {
        endPoint = String.format(EndpointURLs.DELETE_A_PROJECT + getProjectID);
    }

    @Then("I receive a valid Response for Delete a project")
    public void i_receive_valid_Response_for_delete_a_project()
    {
        ReusableFunctions.thenFunction(HTTP_RESPONSE_NO_CONTENT);
    }

}

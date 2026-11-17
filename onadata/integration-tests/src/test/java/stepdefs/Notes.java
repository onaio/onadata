package stepdefs;

import config.EndpointURLs;
import cucumber.api.java.en.And;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;
import payloads.NotesPayload;
import validation.NotesValidation;

import static config.EnvGlobals.*;
import static stepdefs.Hooks.RequestPayLoad;
import static stepdefs.Hooks.endPoint;
import static general.GeneralFunctions.generateAlphaNumeric;

public class Notes {

    @Given("I Set Add a note to a submission")
    public void iSetAddANoteToASubmission() {
        endPoint = EndpointURLs.ADD_A_NOTE;
        newNote = generateAlphaNumeric( "New Note", 2);
        RequestPayLoad = NotesPayload.createNote(newNote);

    }


    @Then("I receive a valid Response for adding a note")
    public void iReceiveAValidResponseForAddingANote() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
        getNoteID = ReusableFunctions.getResponsePath("id");
        NotesValidation.validateNotesResponse(newNote);

    }

    @Given("I Set Get list of notes api endpoint")
    public void i_Set_GET_list_of_notes_api_endpoint() {
        endPoint = EndpointURLs.GET_LIST_OF_ALL_NOTES;
    }

    @Then("I receive valid Response for Get list of notes service")
    public void i_receive_valid_Response_for_get_list_of_notes_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get notes in submission api endpoint")
    public void i_Set_GET_notes_in_submission_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_NOTES_IN_SUBMISSION + instance);
    }

    @Then("I receive valid Response for Get notes in submission service")
    public void i_receive_valid_Response_for_Get_notes_in_submission_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @And("I Set Delete a note")
    public void iSetDeleteANote() {
        endPoint = String.format(EndpointURLs.DELETE_A_NOTE + getNoteID);

    }

    @Then("I receive a valid Response for deleting a note")
    public void iReceiveAValidResponseForDeletingANote() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_NO_CONTENT);
    }
}

package stepdefs;

import config.EndpointURLs;
import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;

import payloads.ReviewsPayload;
import validation.ReviewsValidation;

import static config.EnvGlobals.*;
import static stepdefs.Hooks.RequestPayLoad;
import static stepdefs.Hooks.endPoint;
import static general.GeneralFunctions.generateAlphaNumeric;

public class Reviews {
    @Given("I Set POST make submission review api endpoint")
    public void i_Set_Post_make_submission_review_api_endpoint() {
        endPoint = EndpointURLs.MAKE_SUBMISSION_REVIEW;
        reviewNote = generateAlphaNumeric("This looks great", 2);
        RequestPayLoad = ReviewsPayload.makeReviews(reviewNote);
    }

    @Then("I receive valid Response for make submission review service")
    public void i_receive_valid_Response_for_make_submission_review_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
        ReviewsValidation.validateReviewResponse(reviewNote);
        getReviewID = ReusableFunctions.getResponsePath( "id");
    }

    @Given("I Set GET submission review api endpoint")
    public void i_Set_Get_submission_review_api_endpoint() {
        endPoint = String.format(EndpointURLs.GET_SUBMISSION_REVIEW.replace("{id}", getReviewID));
    }

    @Then("I receive valid Response for Get submission review service")
    public void i_receive_valid_Response_for_Get_submission_review_service() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set Get list of submission reviews")
    public void i_Set_Get_list_of_submission_reviews(){
        endPoint = EndpointURLs.GET_LIST_OF_SUBMISSION_REVIEWS;
    }

    @Then("I receive a valid Response for getting list of submission reviews")
    public void i_recive_a_valid_Response_for_getting_list_of_submission_reviews(){
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set filter reviews by instance")
    public void i_Set_filter_reviews_by_instance(){
        endPoint = String.format(EndpointURLs.FILTER_REVIEW_BY_INSTANCE + instance);
    }

    @Then("I receive a valid Response for filter reviews by instance")
    public void i_receive_a_valid_Response_for_filter_reviews_by_instance(){
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }

    @Given("I Set filter reviews by status")
    public void i_Set_filter_reviews_by_status(){
        endPoint = EndpointURLs.FILTER_REVIEW_BY_STATUS;
    }

    @Then("I receive a valid Response for filtering reviews by status")
    public void i_receive_a_valid_Response_for_filtering_reviews_by_status(){

    }

}

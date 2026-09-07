package stepdefs;



import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;
import payloads.OrganizationsPayloads;
import config.EndpointURLs;
import validation.OrganizationValidation;

import static config.EnvGlobals.orgName;
import static config.EnvGlobals.orgUserName;
import static stepdefs.Hooks.RequestPayLoad;
import static stepdefs.Hooks.endPoint;
import static general.GeneralFunctions.generateAlphaNumeric;

public class Organizations {
    @Given("I Set Create an organization")
    public void iSetCreateAnOrganization() {
        endPoint = EndpointURLs.CREATE_AN_ORGANIZATION;
        orgUserName = generateAlphaNumeric("testorg", 4);
        orgName = generateAlphaNumeric("Test Org", 4);
        RequestPayLoad = OrganizationsPayloads.createOrganization(orgUserName, orgName);

    }


    @Then("I receive a valid Response for  creating an organization")
    public void iReceiveAValidResponseForCreatingAnOrganization() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
        orgUserName = ReusableFunctions.getResponsePath("org");
        OrganizationValidation.validateOrganizationResponse(orgUserName, orgName);
        
    }

    @Given("I Set Get list of organizations")
    public void iSetGetListOfOrganizations() {
        endPoint = EndpointURLs.LIST_ORGANIZATIONS;
    }

    @Then("I receive a valid Response for Get list of organizations")
    public void iReceiveAValidResponseForGetListOfOrganizations() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        
    }

    @Given("I Set list organizations shared with another user")
    public void iSetListOrganizationsSharedWithAnotherUser() {
        endPoint = EndpointURLs.ORG_SHARED_WITH_ANOTHER_USER;

    }

    @Then("I receive a valid Response for listing organizations shared with another user")
    public void iReceiveAValidResponseForListingOrganizationsSharedWithAnotherUser() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set Retrieve organization profile information")
    public void iSetRetrieveOrganizationProfileInformation() {
        endPoint = String.format(EndpointURLs.RETRIEVE_ORG_PROFILE + orgUserName);
    }


    @Then("I receive a valid Response for retrieving organization profile information")
    public void iReceiveAValidResponseForRetrievingOrganizationProfileInformation() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set Update organization profile")
    public void iSetUpdateOrganizationProfile() {
        endPoint = String.format(EndpointURLs.UPDATE_ORG_PROFILE + orgUserName);
        RequestPayLoad = OrganizationsPayloads.updateOrganization();
    }


    @Then("I receive a valid Response for updating organization profile")
    public void iReceiveAValidResponseForUpdatingOrganizationProfile() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set Add a user to an organization")
    public void iSetAddAUserToAnOrganization() {
        endPoint = String.format(EndpointURLs.ADD_USER_TO_ORG.replace("{name}", orgUserName));
        RequestPayLoad = OrganizationsPayloads.addMember();
    }

    @Then("I receive a valid Response for adding a user to an organization")
    public void iReceiveAValidResponseForAddingAUserToAnOrganization() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);

    }

    @Given("I Set List organization members")
    public void iSetListOrganizationMembers() {
        endPoint = String.format(EndpointURLs.LIST_ORG_MEMBERS.replace("{name}", orgUserName));
    }

    @Then("I receive a valid Response for listing organization members")
    public void iReceiveAValidResponseForListingOrganizationMembers() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set Update member role")
    public void iSetUpdateMemberRole() {
        endPoint = String.format(EndpointURLs.UPDATE_MEMBER_ROLE.replace("{name}", orgUserName));
        RequestPayLoad = OrganizationsPayloads.updateMemberRole();
    }

    @Then("I receive a valid Response for updating member role")
    public void iReceiveAValidResponseForUpdatingMemberRole() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);

    }

    @Given("I Set Remove member from organization")
    public void iSetRemoveMemberFromOrganization() {
        endPoint = String.format(EndpointURLs.REMOVE_MEMBER_FROM_ORG.replace("{name}", orgUserName));
        RequestPayLoad = OrganizationsPayloads.deleteMember();
    }


    @Then("I receive a valid Response for removing member from organization")
    public void iReceiveAValidResponseForRemovingMemberFromOrganization() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
    }


}

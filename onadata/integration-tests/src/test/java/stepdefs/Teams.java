package stepdefs;


import config.EndpointURLs;

import cucumber.api.java.en.Given;
import cucumber.api.java.en.Then;
import general.ReusableFunctions;
import org.json.JSONArray;
import payloads.TeamsPayload;

import static config.EnvGlobals.teamID;
import static stepdefs.Hooks.RequestPayLoad;
import static stepdefs.Hooks.endPoint;

public class Teams {
    @Given("I Set Get list of teams")
    public void iSetGetListOfTeams() {
        endPoint = EndpointURLs.GET_LIST_OF_TEAMS;

    }

    @Then("I receive a valid Response for Get list of teams")
    public void iReceiveAValidResponseForGetListOfTeams() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);
        JSONArray getTeamsKey = ReusableFunctions.getResponseJson("teamid", "name");

        teamID = String.valueOf(getTeamsKey.getJSONObject(0).getInt("teamid"));

        System.out.println(teamID);

    }

    @Given("I Set Filter team by organization")
    public void iSetFilterTeamByOrganization() {
        endPoint = EndpointURLs.FILTER_TEAM_BY_ORG;
    }

    @Then("I receive a valid Response for filtering teams by organization")
    public void iReceiveAValidResponseForFilteringTeamsByOrganization() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set Filter team by id {string}")
    public void iSetFilterTeamById(String string) {
        endPoint = String.format(EndpointURLs.FILTER_TEAM_BY_ID + teamID);
    }

    @Then("I receive a valid Response for filtering a team by id")
    public void iReceiveAValidResponseForFilteringATeamById() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set Add a user to a team {string}")
    public void iSetAddAUserToATeam(String string) {
        endPoint = String.format(EndpointURLs.ADD_USER_TO_TEAM.replace("{id}", teamID));
        RequestPayLoad = TeamsPayload.addMember();

    }

    @Then("I receive a valid Response for adding a user to a team")
    public void iReceiveAValidResponseForAddingAUserToATeam() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);

    }

    @Given("I Set List members of a team {string}")
    public void iSetListMembersOfATeam(String string) {
        endPoint = String.format(EndpointURLs.LIST_MEMBERS_OF_A_TEAM.replace("{id}", teamID));
    }

    @Then("I receive a valid Response for listing members of a team")
    public void iReceiveAValidResponseForListingMembersOfATeam() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_SUCCESS);

    }

    @Given("I Set team member permission on project {string}")
    public void iSetTeamMemberPermissionOnProject(String string) {
        endPoint = String.format(EndpointURLs.TEAM_PERMISSION_IN_PROJECT.replace("{id}", teamID));
        RequestPayLoad = TeamsPayload.teamPermission();
    }

    @Then("I receive a valid Response for setting team member permission on project")
    public void iReceiveAValidResponseForSettingTeamMemberPermissionOnProject() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_NO_CONTENT);
    }

    @Given("I Set remove team member from team {string}")
    public void iSetRemoveTeamMemberFromTeam(String string) {
        endPoint = String.format(EndpointURLs.REMOVE_MEMBER_FROM_TEAM.replace("{id}", teamID));
        RequestPayLoad = TeamsPayload.deleteMember();
    }

    @Then("I receive a valid Response for removing team member from team")
    public void iReceiveAValidResponseForRemovingTeamMemberFromTeam() {
        ReusableFunctions.thenFunction(Hooks.HTTP_RESPONSE_CREATED);
    }
}

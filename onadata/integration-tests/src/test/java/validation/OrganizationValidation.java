package validation;

import general.ReusableFunctions;
import org.junit.Assert;

public class OrganizationValidation {

    public static String USERNAME = "org";

    public static String NAME = "name";

    public static void validateOrganizationResponse (String orgUserName, String orgName){
        Assert.assertEquals(ReusableFunctions.getResponsePath(USERNAME), orgUserName);
        Assert.assertEquals(ReusableFunctions.getResponsePath(NAME), orgName);
    }
}

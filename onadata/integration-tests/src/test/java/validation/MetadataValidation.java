package validation;

import general.ReusableFunctions;
import org.junit.Assert;

public class MetadataValidation {

    public static String ID = "id";

    public static String FORMID = "xform";

    public static void validateMetadataResponse(){
        Assert.assertNotNull(ReusableFunctions.getResponsePath(ID));
        Assert.assertNotNull(ReusableFunctions.getResponsePath(FORMID));
    }
}

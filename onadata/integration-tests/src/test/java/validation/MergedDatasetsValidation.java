package validation;

import general.ReusableFunctions;
import org.junit.Assert;

public class MergedDatasetsValidation {

    public static final String ID = "id";

    public static final String TITLE = "title";

    public static void validateMergedResponse(String datasetTitle){
        Assert.assertNotNull(ReusableFunctions.getResponsePath(ID));
        Assert.assertEquals(ReusableFunctions.getResponsePath(TITLE), datasetTitle);
    }
}

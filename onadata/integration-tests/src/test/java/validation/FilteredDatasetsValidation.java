package validation;

import general.ReusableFunctions;
import org.junit.Assert;


public class FilteredDatasetsValidation {

    public static final String  ID = "dataviewid";

    public static final String NAME = "name";

    public static void validateDatasetResponse(String datasetName) {
        Assert.assertNotNull(ReusableFunctions.getResponsePath(ID));
        Assert.assertEquals(ReusableFunctions.getResponsePath(NAME), datasetName);
    }

}

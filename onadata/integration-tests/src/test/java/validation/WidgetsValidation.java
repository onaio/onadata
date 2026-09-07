package validation;

import general.ReusableFunctions;
import org.junit.Assert;

public class WidgetsValidation {

    public static final String ID = "id";

    public static final String KEY = "key";

    public static final String TITLE = "title";

    public static void validateWidgetResponse(String widgetTitle){
        Assert.assertNotNull(ReusableFunctions.getResponsePath(ID));
        Assert.assertNotNull(ReusableFunctions.getResponsePath(KEY));
        Assert.assertEquals(ReusableFunctions.getResponsePath(TITLE), widgetTitle);
    }
}

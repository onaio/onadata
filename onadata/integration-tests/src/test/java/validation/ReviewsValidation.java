package validation;

import general.ReusableFunctions;
import org.junit.Assert;

public class ReviewsValidation {

    public static final String ID = "id";

    public static final String STATUS = "status";

    public static final String NOTE = "note";

    public static void validateReviewResponse(String reviewNote){
        Assert.assertNotNull(ReusableFunctions.getResponsePath(ID));
        Assert.assertNotNull(ReusableFunctions.getResponsePath(STATUS));
        Assert.assertEquals(ReusableFunctions.getResponsePath(NOTE), reviewNote);
    }

}

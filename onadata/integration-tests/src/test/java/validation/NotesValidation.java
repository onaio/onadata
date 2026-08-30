package validation;

import general.ReusableFunctions;
import org.junit.Assert;

public class NotesValidation {

    public static String ID = "id";

    public static String Note = "note";

    public static String Instance = "instance";

    public static void validateNotesResponse(String newNote){
        Assert.assertNotNull(ReusableFunctions.getResponsePath(ID));
        Assert.assertNotNull(ReusableFunctions.getResponsePath(Instance));
        Assert.assertEquals(ReusableFunctions.getResponsePath(Note), newNote);
    }
}

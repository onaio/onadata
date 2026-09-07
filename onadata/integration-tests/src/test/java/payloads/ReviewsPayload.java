package payloads;

import static config.EnvGlobals.instance;

public class ReviewsPayload {
    public static String makeReviews(String reviewNote)
    {return "{\n" +
            "    \"instance\": "+instance+",\n" +
            "    \"status\": \"1\",\n" +
            "    \"note\": \""+reviewNote+"\"}";
    }
}

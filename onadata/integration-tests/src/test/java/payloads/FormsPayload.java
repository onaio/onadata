package payloads;

public class FormsPayload {
    public static String addTag (String newTag){
        return "{\n" +
                "    \"tags\": \""+newTag+"\"\n" +
                "}";
    }
}

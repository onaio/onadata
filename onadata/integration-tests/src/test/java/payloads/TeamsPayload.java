package payloads;

import static config.EnvGlobals.getProjectID;

public class TeamsPayload {

    public static String addMember (){
        return "{\n" +
                "    \"username\": \"onasupport\"\n" +
                "}";
    }

    public static String teamPermission (){
        return "{\n" +
                "    \"project\": \""+getProjectID+"\",\n" +
                "    \"role\": \"readonly\"\n" +
                "}";
    }

    public static String deleteMember (){
        return "{\n" +
                "    \"username\": \"onasupport\"\n" +
                "}";
    }
}

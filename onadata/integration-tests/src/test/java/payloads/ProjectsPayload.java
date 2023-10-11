package payloads;


import static config.ConfigProperties.baseUrl;
import static config.ConfigProperties.username;
import static config.EnvGlobals.getFormID;
import static config.EnvGlobals.projectName;

public class ProjectsPayload {
    public static String createProject (String projectName){

        return "{\n" +
                "    \"owner\": \""+baseUrl+"/api/v1/users/"+username+"\",\n" +
                "    \"public\": \"true\",\n" +
                "    \"name\": \""+projectName+"\"\n" +
                "}\n";
    }

    public static String updateProject (String location){
        return "{\n" +
                "    \"description\": \"Updated via API\",\n" +
                "    \"location\": \""+location+"\",\n" +
                "    \"category\": \"energy\",\n" +
                "    \"public\":\"true\",\n" +
                "    \"owner\": \""+baseUrl+"/api/v1/users/"+username+"\",\n" +
                "    \"public\":\"false\",\n" +
                "    \"name\":\""+projectName+"\"\n" +
                "}\n";
    }

    public static String assignForm () {
        return "{\n" +
                "    \"formid\": \""+getFormID+"\"\n" +
                "}";
    }
    public static String tagProject (String tag){
        return "{\n" +
                "    \"tags\": \"epic, magnificent, autonomous, grand,"+tag+"\"\n" +
                "}";
    }

}

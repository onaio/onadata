package payloads;

import static config.ConfigProperties.baseUrl;
import static config.EnvGlobals.*;

public class MergedDatasetPayload {
    public static String mergeDatasets(String datasetTitle)
    {return "{\n" +
            "    \"name\": \""+datasetTitle+"\",\n" +
            "    \"xforms\": [\n" +
            "        \""+baseUrl+"/api/v1/forms/"+getFormID+"\",\n" +
            "        \""+baseUrl+"/api/v1/forms/"+getFormID2+"\"\n" +
            "    ],\n" +
            "    \"project\":  \""+baseUrl+"/api/v1/projects/"+getProjectID+"\"\n" +
            "}";}
}

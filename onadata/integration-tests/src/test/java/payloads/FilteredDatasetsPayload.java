package payloads;

import static config.ConfigProperties.baseUrl;
import static config.EnvGlobals.getFormID;
import static config.EnvGlobals.getProjectID;

public class FilteredDatasetsPayload {

    public static String createDataset(String datasetName)
    {return "{\n" +
            "    \"name\": \""+datasetName+"\",\n" +
            "    \"xform\": \""+baseUrl+"/api/v1/forms/"+getFormID+"\",\n" +
            "    \"project\":  \""+baseUrl+"/api/v1/projects/"+getProjectID+"\",\n" +
            "    \"columns\": [\"resp_name\", \"good_or_bad\", \"flavour\", \"resp_age\"],\n" +
            "    \"query\": [{\"column\":\"resp_age\", \"filter\":\">\", \"value\":\"32\"}]\n" +
            "}";}

    public static String updateDataset(String datasetName)
    {return "{\n" +
            "    \"name\": \""+datasetName+"\",\n" +
            "    \"xform\": \""+baseUrl+"/api/v1/forms/"+getFormID+"\",\n"+
            "    \"project\":  \""+baseUrl+"/api/v1/projects/"+getProjectID+"\",\n" +
            "    \"columns\": [\"resp_name\", \"good_or_bad\", \"flavour\", \"resp_age\"],\n" +
            "    \"query\": [{\"column\":\"resp_age\", \"filter\":\">\", \"value\":\"25\"}]\n" +
            "}";}

    public static String patchDataset(String datasetName)
    {return "{\n" +
            "    \"name\": \""+datasetName+"\",\n" +
            "    \"xform\": \""+baseUrl+"/api/v1/forms/"+getFormID+"\",\n" +
            "    \"project\":  \""+baseUrl+"/api/v1/projects/"+getProjectID+"\",\n" +
            "    \"columns\": [\"resp_name\", \"good_or_bad\", \"flavour\", \"resp_age\", \"dominant_flavour\"],\n" +
            "    \"query\": [{\"column\":\"resp_age\", \"filter\":\">\", \"value\":\"32\"}]\n" +
            "}";}
}

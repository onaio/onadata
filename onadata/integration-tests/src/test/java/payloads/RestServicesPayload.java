package payloads;

import static config.EnvGlobals.getFormID;

public class RestServicesPayload {

    public static String addRestService (){
        return "{\n" +
                "    \"xform\": \""+getFormID+"\", \n" +
                "    \"service_url\": \"https://rapidpro.ona.io/api/v2/flow_starts.json\",\n" +
                "    \"name\": \"textit\",\n" +
                "    \"auth_token\": \"d7d083ce3d319c0d65c3bc740a570aa231e1b49c\",\n" +
                "    \"flow_uuid\": \"50dde9fc-84a9-4f0f-95c8-2e5158b2ef8d\",\n" +
                "    \"contacts\": \"+254712345890\"\n" +
                "\n" +
                "    }";

    }

    public static String addGoogleSheet (){
        return "{\n" +
                "    \"xform\":\""+getFormID+"\",\n" +
                "    \"name\": \"google_sheets\",\n" +
                "    \"google_sheet_title\": \"population-sync\",\n" +
                "    \"send_existing_data\": true,\n" +
                "    \"sync_updates\": false,\n" +
                "    \"redirect_uri\": \"https://stage-api.ona.io\"\n" +
                "}";
    }
}

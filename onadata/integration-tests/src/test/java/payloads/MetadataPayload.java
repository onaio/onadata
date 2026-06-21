package payloads;

import static config.EnvGlobals.getFormID;

public class MetadataPayload {

    public static String createMetadata (){
        return "{\n" +
                "    \"xform\":\""+getFormID+"\", \n" +
                "    \"data_type\": \"mapbox_layer\", \n" +
                "    \"data_value\": \"https://api.mapbox.com/styles/v1/kaymutua/clgytbt4r00gi01pn48hpa4dc/tiles/256/" +
                "{z}/{x}/{y}@2x?access_token=pk.eyJ1Ijoia2F5bXV0dWEiLCJhIjoiY2pnZXk0Z2I0M25zeDMzbGkyZHcwMmRpcyJ9" +
                ".zZtRK2iKZXMCufUZ8ogJEw\"\n" +
                "}";
    }
}

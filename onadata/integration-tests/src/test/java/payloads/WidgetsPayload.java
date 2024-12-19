package payloads;

import static config.ConfigProperties.baseUrl;

public class WidgetsPayload {

    public static String createWidgets(String widgetTitle, String formid)
    {return "{\n" +
            "    \"title\": \""+widgetTitle+"\",\n" +
            "    \"description\": \"new description\",\n" +
            "    \"aggregation\": \"mean\",\n" +
            "    \"order\": 0,\n" +
            "    \"content_object\": \""+baseUrl+"/api/v1/forms/"+formid+"\",\n" +
            "    \"widget_type\": \"charts\",\n" +
            "    \"view_type\": \"horizontal-bar\",\n" +
            "    \"column\": \"dominant_flavour\"\n" +
            "}"; }

    public static String updateWidgets(String widgetTitle, String formid)
    {return "{\n" +
            "    \"title\": \""+widgetTitle+"\",\n" +
            "    \"description\": \"new description\",\n" +
            "    \"aggregation\": \"mean\",\n" +
            "    \"order\": 0,\n" +
            "    \"content_object\": \""+baseUrl+"/api/v1/forms/"+formid+"\",\n" +
            "    \"widget_type\": \"charts\",\n" +
            "    \"view_type\": \"horizontal-bar\",\n" +
            "    \"column\": \"dominant_flavour\"\n" +
            "}"; }

    public static String patchWidgets()
    {return "{\n" +
            "    \"column\": \"resp_age\"\n" +
            "}";}
}

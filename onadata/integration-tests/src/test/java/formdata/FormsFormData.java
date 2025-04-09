package formdata;

import general.ReusableFunctions;

import java.util.Map;

import static config.EnvGlobals.getProjectID;

import static config.ConfigProperties.username;

public class FormsFormData {

    public static Map<String, String> replaceForm (){
        return ReusableFunctions.form_data("public","False", "description", "Just a test form");
    }

    public static Map<String, String> cloneForm (){
        return ReusableFunctions.form_data("username", username, "project", getProjectID);
    }
}

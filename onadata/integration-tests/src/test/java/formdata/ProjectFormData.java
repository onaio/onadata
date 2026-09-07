package formdata;

import general.ReusableFunctions;

import java.util.Map;

public class ProjectFormData {

    public static Map<String, String> shareProject (){
        return ReusableFunctions.form_data("username","fmutua","role","editor");
    }

    public static Map<String, String> shareMultiple (){
        return ReusableFunctions.form_data( "username", "onasupport,qastuff,nishm", "role", "readonly");
    }

    public static Map<String, String> sendEmail (){
        return ReusableFunctions.form_data( "username", "fkanini", "role", "dataentry", "email_msg",
                "I have shared a project with you");
    }

    public static Map<String, String> removeUser (){
        return ReusableFunctions.form_data("username","fmutua","role","editor","remove","true");
    }

}

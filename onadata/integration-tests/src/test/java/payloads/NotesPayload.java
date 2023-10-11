package payloads;

import static config.EnvGlobals.instance;

public class NotesPayload {

    public static String createNote (String newNote){
        return "{\n" +
                "        \"note\": \""+newNote+"\",\n" +
                "        \"instance\": \""+instance+"\"\n" +
                "        }";

    }
}



package payloads;

public class OrganizationsPayloads {

    public static String createOrganization (String orgUserName, String orgName) {
        return "{\n" +
                "    \"org\": \""+orgUserName+"\",\n" +
                "    \"name\": \""+orgName+"\",\n" +
                "    \"email\": \"modilabs@localhost.com\",\n" +
                "    \"city\": \"New York\",\n" +
                "    \"country\": \"US\"\n" +
                "}";
    }

    public static String updateOrganization () {
        return "{\n" +
                "    \"metadata\": \n" +
                "    [\n" +
                "        \"metadata1\", \"metadata2\"\n" +
                "        \n" +
                "    ]\n" +
                "    \n" +
                "    }";

    }

    public static String addMember (){
        return "{\n" +
                "    \"username\": \"onasupport\"\n" +
                "    \n" +
                "    }";
    }

    public static String updateMemberRole (){
        return "{\n" +
                "    \"username\": \"onasupport\", \n" +
                "    \"role\": \"editor\"\n" +
                "    \n" +
                "    }";
    }

    public static String deleteMember(){
        return "{\n" +
                "    \"username\": \"onasupport\"\n" +
                "    \n" +
                "    }";
    }
}

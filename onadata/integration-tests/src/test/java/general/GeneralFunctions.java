package general;


import org.apache.commons.lang3.RandomStringUtils;

import java.util.*;

public class GeneralFunctions
{

    public static Date getTime() {
        Calendar calendar = Calendar.getInstance();
        return calendar.getTime();
    }

    public static String generateAlphaNumeric(String s, int length)
    {
        String RawRandomNumber = RandomStringUtils.randomNumeric(length);
        StringBuilder stringBuilder = new StringBuilder();
        stringBuilder.append(s);
        stringBuilder.append(RawRandomNumber);
        return stringBuilder.toString();
    }

}
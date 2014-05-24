## JSON Rest API

OnaData provides the following JSON api endpoints:

* [/api/v1/users](/api/v1/users) - List, Retrieve username, first
and last name
* [/api/v1/profiles](/api/v1/profiles) - List, Create,
Update, user information
* [/api/v1/orgs](/api/v1/orgs) - List, Retrieve, Create,
Update organization and organization info
* [/api/v1/projects](/api/v1/projects) - List, Retrieve, Create,
 Update organization projects, forms
* [/api/v1/teams](/api/v1/teams) - List, Retrieve, Create,
Update teams
* [/api/v1/forms](/api/v1/forms) - List, Retrieve
xlsforms information
* [/api/v1/data](/api/v1/data) - List, Retrieve submission data

## Status Codes

* **200** - Successful [`GET`, `PATCH`, `PUT`]
* **201** - Resource successfully created [`POST`]
* **204** - Resouce successfully deleted [`DELETE`]
* **403** - Permission denied to resource
* **404** - Resource was not found

## Authentication

OnaData JSON API enpoints support both Basic authentication
and API Token Authentication through the `Authorization` header.

### Basic Authentication

Example using curl:

    curl -X GET https://formhub.org/api/v1 -u username:password

### Token Authentication

Example using curl:

    curl -X GET https://formhub.org/api/v1 -H "Authorization: Token TOKEN_KEY"

### OnaData Tagging API

* [Filter form list by tags.](
/api/v1/forms#get-list-of-forms-with-specific-tags)
* [List Tags for a specific form.](
/api/v1/forms#get-list-of-tags-for-a-specific-form)
* [Tag Forms.](/api/v1/forms#tag-forms)
* [Delete a specific tag.](/api/v1/forms#delete-a-specific-tag)
* [List form data by tag.](
/api/v1/data#query-submitted-data-of-a-specific-form-using-tags)
* [Tag a specific submission](/api/v1/data#tag-a-submission-data-point)

## Using Oauth2 with formhub API

You can learn more about oauth2 [here](
http://tools.ietf.org/html/rfc6749).

### 1. Register your client application with formhub - [register](\
/o/applications/register/)

- `name` - name of your application
- `client_type` - Client Type: select confidential
- `authorization_grant_type` - Authorization grant type: Authorization code
- `redirect_uri` - Redirect urls: redirection endpoint

Keep note of the `client_id` and the `client_secret`, it is required when
 requesting for an `access_token`.

### 2. Authorize client application.

The authorization url is of the form:

<pre class="prettyprint">
<b>GET</b> /o/authorize?client_id=XXXXXX&response_type=code&state=abc</pre>

example:

    http://localhost:8000/o/authorize?client_id=e8&response_type=code&state=xyz

Note: Providing the url to any user will prompt for a password and
request for read and write permission for the application whose `client_id` is
specified.

Where:

- `client_id` - is the client application id - ensure its urlencoded
- `response_type` - should be code
- `state` - a random state string that you client application will get when
   redirection happens

What happens:

1. a login page is presented, the username used to login determines the account
   that provides access.
2. redirection to the client application occurs, the url is of the form:

>   REDIRECT_URI/?state=abc&code=YYYYYYYYY

example redirect uri

    http://localhost:30000/?state=xyz&code=SWWk2PN6NdCwfpqiDiPRcLmvkw2uWd

- `code` - is the code to use to request for `access_token`
- `state` - same state string used during authorization request

Your client application should use the `code` to request for an access_token.

### 3. Request for access token.

Request:

<pre class="prettyprint">
<b>POST</b>/o/token</pre>

Payload:

    grant_type=authorization_code&code=YYYYYYYYY&client_id=XXXXXX&redirect_uri=http://redirect/uri/path

curl example:

    curl -X POST -d "grant_type=authorization_code&\
    code=PSwrMilnJESZVFfFsyEmEukNv0sGZ8&\
    client_id=e8x4zzJJIyOikDqjPcsCJrmnU22QbpfHQo4HhRnv&\
    redirect_uri=http://localhost:30000" "http://localhost:8000/o/token/"\
    --user "e8:xo7i4LNpMj"

Response:

    {
        "access_token": "Q6dJBs9Vkf7a2lVI7NKLT8F7c6DfLD",
        "token_type": "Bearer", "expires_in": 36000,
        "refresh_token": "53yF3uz79K1fif2TPtNBUFJSFhgnpE",
        "scope": "read write groups"
    }

Where:

- `access_token` - access token - expires
- `refresh_token` - token to use to request a new `access_token` in case it has
   expored.

Now that you have an `access_token` you can make API calls.

### 4. Accessing the OnaData API using the `access_token`.

Example using curl:

    curl -X GET https://formhub.org/api/v1 -H "Authorization: Bearer ACCESS_TOKEN"


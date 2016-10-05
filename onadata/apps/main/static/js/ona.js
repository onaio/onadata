(function() {
  'use strict';

  // This config stores the important strings needed to
  // connect to the foursquare API and OAuth service
  //
  // Storing these here is insecure for a public app
  // See part II. of this tutorial for an example of how
  // to do a server-side OAuth flow and avoid this problem
  var config = {
      clientId: 'thho5qsMKvSBhnZfc7OgHpmfQohT3EYpjNsnFvLs',
  };

  // Called when web page first loads and when
  // the OAuth flow returns to the page
  //
  // This function parses the access token in the URI if available
  // It also adds a link to the foursquare connect button
  $(document).ready(function() {
      var accessToken = parseAccessToken();
      var hasAuth = accessToken && accessToken.length > 0;
      updateUIWithAuthState(hasAuth);
      if(hasAuth){
        Cookies.set("accessToken", accessToken);
       }

      $("#connectbutton").click(function() {
          doAuthRedirect();
      });

      $("#getdatabutton").click(function() {
          var formid = $('input[name=formid]')[0].value.trim();
          tableau.connectionName = "OnaData Connector";

          var http = location.protocol;
          var slashes = http.concat("//");
          var host = slashes.concat(window.location.hostname);
          var host = host + (location.port ? ':'+location.port: '');
          var jsonUrl = host + "/api/v1/data/" + formid +".json?sort={\"_id\":1}"
          var conData = {"jsonUrl": jsonUrl};
          tableau.connectionData = JSON.stringify(conData);
          tableau.submit();
      });
  });

  // An on-click funcion for the connect to foursquare button,
  // This will redirect the user to a foursquare login
  function doAuthRedirect() {
      console.log(config);
      var clientId = $('input[name=clientid]')[0].value.trim();

      // update config map
      if(clientId && clientId.length > 0){
        config['clientId'] = clientId
      }
      var appId = config.clientId;
      if (tableau.authPurpose === tableau.authPurposeEnum.ephemerel) {
        appId = config.clientId;
      } else if (tableau.authPurpose === tableau.authPurposeEnum.enduring) {
        appId = config.clientId; // This should be the Tableau Server appID
      }

      var http = location.protocol;
      var slashes = http.concat("//");
      var host = slashes.concat(window.location.hostname);
      var host = host + (location.port ? ':'+location.port: '');
      var redirect_uri = host + "/connector"
      var url = host + '/o/authorize?response_type=token&client_id=' + appId +
              '&redirect_uri=' + redirect_uri;
      window.location.href = url;
  }

  function parseAccessToken() {
    var query = window.location.hash.substring(1);
    var vars = query.split("&");
    var ii;
    for (ii = 0; ii < vars.length; ++ii) {
       var pair = vars[ii].split("=");
       if (pair[0] == "access_token") { return pair[1]; }
    }
    return(false);
   }


  // This function togglels the label shown depending
  // on whether or not the user has been authenticated
  function updateUIWithAuthState(hasAuth) {
      if (hasAuth) {
          $(".notsignedin").css('display', 'none');
          $(".signedin").css('display', 'block');
          $(".getClientId").css('display', 'none');
          $(".getData").css('display', 'block');
      } else {
          $(".notsignedin").css('display', 'block');
          $(".signedin").css('display', 'none');
          $(".getClientId").css('display', 'block');
          $(".getData").css('display', 'none');
      }
  }
  
  // Takes a hierarchical javascript object and tries to turn it into a table
  // Returns an object with headers and the row level data
  function _jsToTable(objectBlob) {
    var rowData = _flattenData(objectBlob);
    _cleanRowData(rowData);
    var headers = _extractHeaders(rowData);
    return {"headers":headers, "rowData":rowData};
  }

  // Given an object:
  //   - finds the longest array in the object
  //   - flattens each element in that array so it is a single object with many properties
  // If there is no array that is a descendent of the original object, this wraps
  // the input in a single element array.
  function _flattenData(objectBlob) {
    // first find the longest array
    var longestArray = _findLongestArray(objectBlob, []);
    if (!longestArray || longestArray.length == 0) {
      // if no array found, just wrap the entire object blob in an array
      longestArray = [objectBlob];
    }
    for (var ii = 0; ii < longestArray.length; ++ii) {
      _flattenObject(longestArray[ii]);
    }
    return longestArray;
  }

  // Given an object with hierarchical properties, flattens it so all the properties
  // sit on the base object.
  function _flattenObject(obj) {
    for (var key in obj) {
      if (obj.hasOwnProperty(key) && typeof obj[key] == 'object') {
        var subObj = obj[key];
        _flattenObject(subObj);
        for (var k in subObj) {
          if (subObj.hasOwnProperty(k)) {
            obj[key + '_' + k] = subObj[k];
          }
        }
        delete obj[key];
      }
    }
  }

  // Finds the longest array that is a descendent of the given object
  function _findLongestArray(obj, bestSoFar) {
    if (!obj) {
      // skip null/undefined objects
      return bestSoFar;
    }

    // if an array, just return the longer one
    if (obj.constructor === Array) {
      // I think I can simplify this line to
      // return obj;
      // and trust that the caller will deal with taking the longer array
      return (obj.length > bestSoFar.length) ? obj : bestSoFar;
    }
    if (typeof obj != "object") {
      return bestSoFar;
    }
    for (var key in obj) {
      if (obj.hasOwnProperty(key)) {
        var subBest = _findLongestArray(obj[key], bestSoFar);
        if (subBest.length > bestSoFar.length) {
          bestSoFar = subBest;
        }
      }
    }
    return bestSoFar;
  }

  // Remove slashes from the data
  function _cleanRowData(rowData){
    var toRet = [];
    for (var row = 0; row < rowData.length; ++row) {
      var rowLine = rowData[row];
      Object.keys(rowLine).forEach(function(key) {
        if(key.indexOf("/") >= 0){
            var newkey = key.replace(/\//g , "_")
            rowLine[newkey] = rowLine[key];
            delete rowLine[key];
        }
      });
      toRet[row] = rowLine;
    }
     return toRet;
  }

  // Given an array of js objects, returns a map from data column name to data type
  function _extractHeaders(rowData) {
    var toRet = {};
    for (var row = 0; row < rowData.length; ++row) {
      var rowLine = rowData[row];
      for (var key in rowLine) {
        if (rowLine.hasOwnProperty(key)) {
          if (!(key in toRet)) {
            toRet[key] = _determineType(rowLine[key]);
          }
        }
      }
    }
    return toRet;
  }

  // Given a primitive, tries to make a guess at the data type of the input
  function _determineType(primitive) {
    // possible types: 'float', 'date', 'datetime', 'bool', 'string', 'int'
    if (parseInt(primitive) == primitive) return 'int';
    if (parseFloat(primitive) == primitive) return 'float';
    if (isFinite(new Date(primitive).getTime())) return 'datetime';
    return 'string';
  }

  function isEmpty(ob){
     for(var i in ob){ return false;}
    return true;
  }

  //------------- Tableau WDC code -------------//
  // Create tableau connector, should be called first
  var myConnector = tableau.makeConnector();

  // Init function for connector, called during every phase but
  // only called when running inside the simulator or tableau
  myConnector.init = function(initCallback) {
      tableau.authType = tableau.authTypeEnum.custom;

      // If we are in the auth phase we only want to show the UI needed for auth
      if (tableau.phase == tableau.phaseEnum.authPhase) {
        $("#getdatabutton").css('display', 'none');
      }

      if (tableau.phase == tableau.phaseEnum.gatherDataPhase) {
        // If API that WDC is using has an endpoint that checks
        // the validity of an access token, that could be used here.
        // Then the WDC can call tableau.abortForAuth if that access token
        // is invalid.
      }

      var accessToken = Cookies.get("accessToken");
      console.log("Access token is '" + accessToken + "'");
      var hasAuth = (accessToken && accessToken.length > 0) || tableau.password.length > 0;
      updateUIWithAuthState(hasAuth);

      initCallback();

      // If we are not in the data gathering phase, we want to store the token
      // This allows us to access the token in the data gathering phase
      if (tableau.phase == tableau.phaseEnum.interactivePhase || tableau.phase == tableau.phaseEnum.authPhase) {
          if (hasAuth) {
              tableau.password = accessToken;

              if (tableau.phase == tableau.phaseEnum.authPhase) {
                // Auto-submit here if we are in the auth phase
                tableau.submit()
              }

              return;
          }
      }
  };

  // Declare the data to Tableau that we are returning from Foursquare
  myConnector.getSchema = function(schemaCallback) {
      var conData = JSON.parse(tableau.connectionData);
      // Get the 1st record to get the headers
      var url = conData.jsonUrl + "&limit=1";

      var xhr = $.ajax({
          url: url,
          headers: {
            "Authorization": "Bearer " + tableau.password
          },
          dataType: 'json',
          success: function (data) {
              var table_meta = _jsToTable(data);
              console.log("tablle >>>"+table_meta);
              if (table_meta.headers) {
                  var cols = [];
                  var schema = [];
                  var headers = table_meta.headers;

                  for (var fieldName in headers) {
                    if (headers.hasOwnProperty(fieldName)) {
//                       cols.push({ id: fieldName.replace(/\//g , "_"),
                         cols.push({ id: fieldName,
                       dataType: headers[fieldName]});
                    }
                  }

                  
                  var tableInfo = {
                    id: "OnadataTable",
                    alias: "Onadata Connector",
                    incrementColumnId: "_id",
                    columns: cols
                  }

                  schema.push(tableInfo);

                  schemaCallback(schema);
              }
              else {
                  tableau.abortWithError("No results found");
              }
          },
          error: function (xhr, ajaxOptions, thrownError) {
              // WDC should do more granular error checking here
              // or on the server side.  This is just a sample of new API.
              tableau.abortForAuth("Invalid Access Token");
          }
      });
  };

  // This function acutally make the foursquare API call and
  // parses the results and passes them back to Tableau
  myConnector.getData = function(table, doneCallback) {
      var lastId = parseInt(table.incrementValue || -1);
      var dataToReturn = [];
      var hasMoreData = false;

      var accessToken = tableau.password;
      var conData = JSON.parse(tableau.connectionData);
      var connectionUri;

      if(lastId > 0){
        connectionUri = conData.jsonUrl + "&query={\"_id\":{\"\$gt\":"+ lastId +"}}";
      }else{
        connectionUri = conData.jsonUrl;
      }


      var xhr = $.ajax({
          url: connectionUri,
          headers: {
            "Authorization": "Bearer " + tableau.password
          },
          dataType: 'json',
          success: function (data) {
              var table_meta = _jsToTable(data);

              if (table_meta.rowData && !isEmpty(table_meta.headers)) {
                  table.appendRows(table_meta.rowData);
                  doneCallback();
              }
          },
          error: function (xhr, ajaxOptions, thrownError) {
              // WDC should do more granular error checking here
              // or on the server side.  This is just a sample of new API.
              tableau.abortForAuth("Invalid Access Token");
          }
      });
  };


  // Register the tableau connector, call this last
  tableau.registerConnector(myConnector);
})();

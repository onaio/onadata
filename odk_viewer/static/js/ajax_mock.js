// Ajax mocking functionality
// --------------------------
(function () {
    // Constructor
    this.AjaxMock = function (options) {
        this.responses = options.responses || {};
    };

    this.AjaxMock.prototype.ajax = function (xhrParams) {
        var method,
            params,
            response,
            deferred = $.Deferred();

        // Default to `GET`
        method = xhrParams.type || "GET";
        params = void 0;

        // Build url query params from `data` property if `GET`
        if (method === "GET") {
            params = [];
            xhrParams.data = xhrParams.data || {};

            if(typeof(xhrParams.data) !== "string") {
                for(var k in xhrParams.data) {
                    if (xhrParams.data.hasOwnProperty(k)){
                        params.push(k + "=" + xhrParams.data[k]);
                    }
                }
            } else {
                params.push(xhrParams.data);
            }
            params = params.join("&");
        }
        if (params) {
            xhrParams.url += "?" + params;
        }

        // Try to get the url from our defined responses
        try {
            response = this.responses[xhrParams.url][method];
            if (response === void 0) {
                console.error("urls." + xhrParams.url + "." + method + " is not defined.");
                deferred.reject({}, 'error');
            } else {
                deferred.resolve(response, 'success', {});
            }
        } catch (err) {
            deferred.reject({}, 'error', err);
        }

        return deferred.promise();
    };
}).call(this);
// Ajax mocking functionality
// --------------------------
(function () {
    // Constructor
    this.AjaxMock = function (options) {
        this.responses = options.responses || {};
    };

    var predicate_args = [
        'data',
        'dataType'
    ];

    this.AjaxMock.prototype.ajax = function (xhrParams) {
        var method,
            params,
            response,
            deferred = $.Deferred();

        // Default to `GET`
        method = xhrParams.type = xhrParams.type || "GET";

        // Filter responses for matching url and method
        var matching_responses = this.responses.filter(function (r) {
            return r.url === xhrParams.url && r.type === xhrParams.type;
        });

        // Use predicate arguments to further filter the list
        matching_responses = matching_responses.filter( function (r) {
            var is_match = true;
            predicate_args.forEach(function (arg) {
                // Check if the response def or xhr has this arg the use
                // _.isEqual to deep compare
                if(( xhrParams.hasOwnProperty(arg) || r.hasOwnProperty(arg) ) && !_.isEqual(xhrParams[arg], r[arg])){
                    is_match = false;
                }
            });
            return is_match;
        });

        if(matching_responses.length > 1) {
            throw Error("Multiple response definitions matched.");
        } else if(matching_responses.length === 0) {
            console.warn("url " + xhrParams.url + "." + method + " with params " + JSON.stringify(xhrParams) +" is not defined.");
            deferred.reject({}, 'error');
        } else {
            deferred.resolve(matching_responses[0].response, 'success', {});
        }
        return deferred.promise();
    };
}).call(this);
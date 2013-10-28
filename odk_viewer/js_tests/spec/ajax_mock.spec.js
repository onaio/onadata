// Ajax Mock Tests
// ----------------
describe("Ajax Mock", function () {
    var ajax_mock;
    beforeEach(function () {
        ajax_mock = new AjaxMock({
            responses: {
                '/home': {
                    GET: {
                        content: "Some Content"
                    },
                    POST: {
                        content: "Posted Some Content"
                    }
                },
                '/home?x=y&a=b': {
                    GET: {
                        content: "Some Content With Params"
                    },
                    POST: {
                        content: "Posted Some Content With Params"
                    }
                }
            }});
    });

    it("succeeds if the url is defined", function () {
        var response,
            xhr = ajax_mock.ajax({
                url: '/home'
            });

        xhr.done(function (data) {
            response = data;
        });
        expect(response.content).toEqual("Some Content");
    });

    it("fails if the url is not defined", function () {
        var failure = false,
            xhr = ajax_mock.ajax({
                url: '/404'
            });

        xhr.fail(function () {
            failure = true;
        });
        expect(failure).toBe(true);
    });

    // Uses the defined request method
    it("uses the defined request method", function () {
        var response,
            xhr = ajax_mock.ajax({
                url: '/home',
                type: 'POST'
            });

        xhr.done(function (data) {
            response = data;
        });
        expect(response.content).toEqual("Posted Some Content");
    });

    // Test that items passed within the data are converted to url query params
    // when the method is GET
    it("build query params from data option when GET", function () {
        var response,
            xhr = ajax_mock.ajax({
                url: '/home',
                data: {
                    x: 'y',
                    a: 'b'
                }
            });

        xhr.done(function (data) {
            response = data;
        });
        expect(response.content).toEqual("Some Content With Params");
    });
});
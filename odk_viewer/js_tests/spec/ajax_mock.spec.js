// Ajax Mock Tests
// ----------------
describe("Ajax Mock", function () {
    var ajax_mock;
    beforeEach(function () {
        ajax_mock = new AjaxMock({
            responses: [
                {
                    url: '/home',
                    type: 'GET',
                    response: {
                        content: "Got Some Content"
                    }
                },
                {
                    url: '/home',
                    type: 'GET',
                    data: {
                        x: 'y',
                        a: 'b'
                    },
                    response: {
                        content: "Got Some Content With Params"
                    }
                },
                {
                    url: '/home',
                    type: 'POST',
                    response: {
                        content: "Posted Some Content"
                    }
                },
                {
                    url: '/home',
                    type: 'POST',
                    data: {
                        x: 'y',
                        a: 'b'
                    },
                    response: {
                        content: "Posted Some Content With Params"
                    }
                }
            ]
        });
    });

    it("can match a response when params is empty", function () {
        var response = {},
            xhr = ajax_mock.ajax({
                url: '/home'
            });

        xhr.done(function (data) {
            response = data;
        });
        expect(response.content).toEqual("Got Some Content");
    });

    it("can match a response when params is defined", function () {
        var response = {},
            xhr = ajax_mock.ajax({
                url: '/home',
                type: 'POST',
                data: {
                    a: 'b',
                    x: 'y'
                }
            });

        xhr.done(function (data) {
            response = data;
        });
        expect(response.content).toEqual("Posted Some Content With Params");
    });

    it("fails if no match is found", function () {
        var failure = false,
            xhr = ajax_mock.ajax({
                url: '/home',
                data: {}
            });

        xhr.fail(function () {
            failure = true;
        });
        expect(failure).toBe(true);
    });
});
// FH.Form Tests
// --------------
describe("Formhub Form", function () {
    describe("Form Loading", function () {
        var fake_xhr;

        beforeEach(function () {
            fake_xhr = sinon.useFakeXMLHttpRequest();
        });

        afterEach(function () {
            fake_xhr.restore();
        });

        // Test that calling `load`, fetches the form from the specified url
        // and triggers the `load` event on successful load
        it("loads the form from the specified url", function () {
            var request,
                loaded = false,
                form = new FH.Form({}, {url: single_lang_form.url});
            fake_xhr.onCreate = function (xhr) {
                request = xhr;
            };

            form.on('load', function () {
                loaded = true;
            });
            form.load();
            request.respond(200, {}, single_lang_form.response);
            expect(loaded).toBe(true);
        });
    });

    describe("Form API", function () {
        it("extracts languages from multi-lang forms", function () {
            // A fake JSON response
            var resp = {
                    default_language: "default",
                    id_string: "test",
                    name: "test_form",
                    title: "Test FOrm",
                    type: "survey",
                    children: [
                        {
                            name: 'age',
                            type: 'integer',
                            label: {
                                English: 'Age',
                                Swahili: 'Umri'
                            }
                        },
                        {
                            name: 'start',
                            type: 'start'
                        }
                    ]
                },
                form;

            form = new FH.Form({}, {url: '/user/forms/test/form.json'});
            form.set({children: resp.children});
            expect(form.get('languages')).toContain('English');
            expect(form.get('languages')).toContain('Swahili');
        });
    });

    // #### Test parsing questions
    describe("Parse Questions", function () {
        var form,
            parsed,
            raw_questions;

        var fake_xhr;

        beforeEach(function () {
            var request;
            form = new FH.Form({}, {url: single_lang_form.url});
            fake_xhr = sinon.useFakeXMLHttpRequest();
            fake_xhr.onCreate = function (xhr) {
                request = xhr;
            };
            form.load();
            request.respond(200, {}, single_lang_form.response);

            raw_questions = form.get(FH.constants.CHILDREN);
            parsed = FH.Form.parseQuestions(raw_questions);
            expect(parsed).toBeDefined();
            expect(parsed.length).toEqual(8);
        });

        afterEach(function () {
            fake_xhr.restore();
        });

        it("can parse nested questions into a single level", function () {
            // get field names
            var field_names = parsed.map(function (q) {
                return q.name;
            });
            expect(field_names).toContain('start_time');
            expect(field_names).toContain('end_time');
            expect(field_names).not.toContain('instruction_note');
            expect(field_names).toContain('location');
            expect(field_names).toContain('nearest_watering_hole');
            expect(field_names).toContain('rating');
            expect(field_names).not.toContain('a_group');
            expect(field_names).toContain('how_epic');
            expect(field_names).toContain('how_delectible');
        });

        it("sets id from fields name for top level children", function () {
            var nearest_watering_hole = _.find(parsed, function (q) {
                return q.name === 'nearest_watering_hole';
            });
            expect(nearest_watering_hole).toBeDefined();
            expect(nearest_watering_hole.xpath).toEqual(nearest_watering_hole.name);
        });

        it("sets id from fields parent's name and name for nested children", function () {
            var how_epic = _.find(parsed, function (q) {
                return q.name === 'how_epic';
            });
            expect(how_epic).toBeDefined();
            expect(how_epic.xpath).toEqual(['a_group', how_epic.name].join('/'));

            var how_delectible = _.find(parsed, function (q) {
                return q.name === 'how_delectible';
            });
            expect(how_delectible).toBeDefined();
            expect(how_delectible.xpath).toEqual(['a_group', how_delectible.name].join('/'));

            var nested_q = _.find(parsed, function (q) {
                return q.name === 'nested_q';
            });
            expect(nested_q).toBeDefined();
            expect(nested_q.xpath).toEqual(['a_group', 'a_nested_group', nested_q.name].join('/'));
        });

        // Test querying for questions by type
        it("can return questions by type", function () {
            var gps_questions = form.questionsByType(FH.types.GEOLOCATION);
            expect(gps_questions.length).toEqual(2);

            var question_names = _.map(gps_questions, function (q) {
                return q.get('name');
            });
            expect(question_names).toContain('location');
            expect(question_names).toContain('nearest_watering_hole');
        });
    });

    // #### Test FH.DataSet API
    describe("Dataset API", function () {
        var fake_server;

        beforeEach(function () {
            fake_server = sinon.fakeServer.create();
            spyOn(Backbone, 'ajax').andCallThrough();

            fake_server.respondWith(location_only_query.response);
        });

        afterEach(function () {
            fake_server.restore();
        });

        it("triggers the load event after loading", function () {
            var data_set,
                loaded = false;

            data_set = new FH.DataSet({}, {url: location_only_query.url});
            data_set.on('load', function () {
                loaded = true;
            });
            data_set.load();
            fake_server.respond();

            expect(loaded).toBe(true);
            expect(Backbone.ajax).toHaveBeenCalled();
        });

        it("can load data only for the specified fields", function () {
            var data_set;

            data_set = new FH.DataSet({}, {url: location_only_query.url});
            data_set.load({fields: ['location']});
            fake_server.respond();
            expect(Backbone.ajax.mostRecentCall.args[0].data.fields).toEqual('["location"]');
        });

        it("can load data with the specified query", function () {
            var data_set;

            data_set = new FH.DataSet({}, {url: location_only_query.url});
            data_set.load({query: {name: "Bob"}});
            fake_server.respond();

            expect(Backbone.ajax.mostRecentCall.args[0].data.query).toEqual('{"name":"Bob"}');
        });

        it("can load data with the specified start", function () {
            var data_set;

            data_set = new FH.DataSet({}, {url: location_only_query.url});
            data_set.load({start: 10});
            fake_server.respond();

            expect(Backbone.ajax.mostRecentCall.args[0].data.start).toEqual('10');
        });
    });

    describe("Field", function () {
        it("returns a fields label when its available", function () {
            var field = new FH.Field({
                name: 'name',
                type: 'text',
                label: 'Your Name'
            });
            expect(field.get('label')).toEqual('Your Name');
        });

        it("it returns a fields name when label is undefined", function () {
            var field = new FH.Field({
                name: 'today',
                type: 'today'
            });

            expect(field.get('label')).toEqual('today');
        });

        it("it returns the specified language's label if defined", function () {
            var field = new FH.Field({
                name: 'age',
                type: 'integer',
                label: {
                    English: 'Age',
                    Swahili: 'Umri'
                }
            });

            expect(field.get('label', 'Swahili')).toEqual('Umri');
        });

        it("it throws an error if the label is multi-lang and a language is not specified", function () {
            var field = new FH.Field({
                    name: 'age',
                    type: 'integer',
                    label: {
                        English: 'Age',
                        Swahili: 'Umri'
                    }
                }),
                fn;
            fn = function () {
                return field.get('label');
            };

            expect(fn).toThrow("You must specify a language");
        });

        describe("Field.languagesFromLabel", function () {
            it("returns a blank list if the field has a string for a label", function () {
                var label = 'Name',
                    result;

                result = FH.Field.languagesFromLabel(label);
                expect(result).toEqual([]);
            });

            it("returns a blank list if the field is undefined", function () {
                var field = {

                    },
                    result;

                result = FH.Field.languagesFromLabel(field.label);
                expect(result).toEqual([]);
            });

            it("returns the list of langauges if label is an object", function () {
                var label = {
                        English: 'Age',
                        Swahili: 'Umri'
                    },
                    result;

                result = FH.Field.languagesFromLabel(label);
                expect(result).toContain('English');
                expect(result).toContain('Swahili');
            });
        });

        describe("FH.Field.isA", function () {
           it("returns true if the typeName is within the type constants", function () {
               var typeName = 'A_type';
               var typeConstants = ['a_type', 'another_type'];
               expect(FH.Field.isA(typeName, typeConstants)).toBe(true);
           });

            it("returns false if the typeName is not within the type constants", function () {
               var typeName = 'a_different_type';
               var typeConstants = ['a_type', 'another_type'];
               expect(FH.Field.isA(typeName, typeConstants)).toBe(false);
           });
        });
    });

    describe("FH.DataSet.GetSortValue", function () {
        it("should return the value as as number", function () {
            var model = new FH.Data({
                    _id: 1,
                    age: "23"
                }),
                fieldId = 'age';

            expect(FH.DataSet.GetSortValue(model, fieldId, parseInt)).toEqual(23);
            expect(FH.DataSet.GetSortValue(model, fieldId, parseFloat)).toEqual(23);
        });

        it("should return 0 if value is not a number", function () {
            var model = new FH.Data({
                    _id: 1,
                    age: "abcd"
                }),
                fieldId = 'age';

            expect(FH.DataSet.GetSortValue(model, fieldId, parseInt)).toEqual(0);
            expect(FH.DataSet.GetSortValue(model, fieldId, parseFloat)).toEqual(0);
        })
    });
});

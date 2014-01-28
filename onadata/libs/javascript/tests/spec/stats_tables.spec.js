describe("Stats Tables", function () {
    describe("SummaryStatsEnabled", function () {
        it("returns true when method contains MEAN, MEDIAN or MODE", function () {
            var result,
                summaryMethod = Ona.SummaryMethod.MEAN | Ona.SummaryMethod.MEDIAN | Ona.SummaryMethod.MODE;

            result = Ona.StatsCollection.StatsSummariesEnabled(summaryMethod);
            expect(result).toBe(true);
        });

        it("returns false when method doest contain any of MEAN, MEDIAN or MODE", function () {
            var result,
                summaryMethod = 0;

            result = Ona.StatsCollection.StatsSummariesEnabled(summaryMethod);
            expect(result).toBe(false);
        });
    });

    describe("Ona.SummaryMethodView", function () {
        describe("setSummaryMethods", function () {
            var summaryMethodView;

            beforeEach(function () {
                summaryMethodView = new Ona.SummaryMethodView({
                    model: new Backbone.Model({
                        fields: new Backbone.Collection(),
                        selected_field: void 0,
                        summary_methods: Ona.SummaryMethod.MODE,
                        languages: [],
                        selected_language: '-1'
                    })
                });
            });

            it("should or the incoming value with the models current summary method's value", function () {
                var currentValue = summaryMethodView.model.get('summary_methods');
                summaryMethodView.setSummaryMethods(Ona.SummaryMethod.MEAN, true);
                expect(summaryMethodView.model.get('summary_methods')).toEqual(currentValue | Ona.SummaryMethod.MEAN);
            });

            it("should xor the incoming value with the models current summary method's value if setBit is false", function () {
                var currentValue = summaryMethodView.model.get('summary_methods');
                summaryMethodView.setSummaryMethods(Ona.SummaryMethod.MEAN, false);
                expect(summaryMethodView.model.get('summary_methods')).toEqual(currentValue ^ Ona.SummaryMethod.MEAN);
            });

        });
    });

    describe("Ona.StatsCollection", function () {
        var statsCollection;

        beforeEach(function () {
            var field = new FH.Field({
                type: 'integer',
                name: 'age',
                label: 'Your Age'
            });
            field.id = 'age';
            statsCollection = new Ona.StatsCollection([], {
                url: '/some/url',
                field: field,
                summaryMethods: Ona.SummaryMethod.MEAN | Ona.SummaryMethod.MEDIAN
            });
        });

        describe("parse", function () {
            it("only returns values for enabled stats", function () {
                var parsedResponse = statsCollection.parse({
                    age: {
                        min: 0,
                        max: 5,
                        mean: 2,
                        mode: 3,
                        median: 4
                    }
                });
                expect(parsedResponse).toEqual([
                    {stat: 'mean', value: 2},
                    {stat: 'median', value: 4}
                ])
            });
        });
    });

    describe("Ona.TableBuilderView", function () {
        describe("ShouldDisableButton", function () {
            it("should return true when selected field is undefined or no summary method is selected", function () {
                var model = new Backbone.Model({
                    selected_field: void 0,
                    summary_methods: 0
                });
                result = Ona.TableBuilderView.ShouldDisableButton(model);
                expect(result).toBe(true);
            });

            it("should return false when selected field is NOT undefined an at least one summary method is selected", function () {
                var model = new Backbone.Model({
                    selected_field: new FH.Field({
                        name: 'age',
                        label: 'Age'
                    }),
                    summary_methods: Ona.SummaryMethod.MEAN
                });
                result = Ona.TableBuilderView.ShouldDisableButton(model);
                expect(result).toBe(false);
            });
        });
    });

    describe("Ona.FrequenciesCollection", function () {
        describe("LabelsForSelect", function () {
            it("should comma separate select multiples", function () {
                var result,
                    field = new FH.Field({
                    name: "browsers",
                    label: "Browsers",
                    children: [
                        {name: "chrome", label: "Chrome"},
                        {name: "ie", label: "Internet Explorer"},
                        {name: "firefox", label: "Mozilla Firefox"}
                    ]
                });
                result = Ona.FrequenciesCollection.LabelsForSelect('chrome ie', field, void 0);
                expect(result).toEqual("Chrome, Internet Explorer")
            });

            it("should return the requested language's label", function () {
                var result,
                    field = new FH.Field({
                    name: "browsers",
                    label: {English: "Browsers", Swahili: "Vifaa vya Mtandao"},
                    children: [
                        {name: "chrome", label: {English: "Chrome", Swahili: "Chromi"}},
                        {name: "ie", label: {English: "Internet Explorer", Swahili: "Internet Exploreri"}},
                        {name: "firefox", label: {English: "Mozilla Firefox", Swahili: "Mozilla Firefoxi"}},
                    ]
                });
                result = Ona.FrequenciesCollection.LabelsForSelect('chrome ie', field, "English");
                expect(result).toEqual("Chrome, Internet Explorer");

                result = Ona.FrequenciesCollection.LabelsForSelect('chrome ie', field, "Swahili");
                expect(result).toEqual("Chromi, Internet Exploreri")
            });
        });
    });
});
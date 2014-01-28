(function () {
    "use strict";
    // Save a reference to the global object (`window` in the browser, `exports`
    // on the server).
    var root = this;

    // Check if the `Ona` namespace already exists and create it otherwise. We'll
    // attach all our exposed objects to it.
    var Ona = root.Ona = root.Ona || {};

    // Summary method constants
    Ona.SummaryMethod = {
        FREQUENCIES: 2 << 0,
        PERCENTAGES: 2 << 1,
        MEAN: 2 << 2,
        MEDIAN: 2 << 3,
        MODE: 2 << 4
    };

    var fieldIsNumeric = function (field) {
        return field.get('type') === 'integer' || field.get('decimal');
    };

    Ona.TableDef = Backbone.Model.extend({

    });


    Ona.QuestionView = Backbone.View.extend({
        template: _.template(
            '<option value="">Select a question</option>' +
            '<% _.each(fields, function (f) {%>' +
              '<option value="<%= f["id"] %>"><%= f["label"] %></option><' +
            '% }); %>'),

        events: {
            'change select': function (evt) {
                var val = $(evt.currentTarget).val();
                this.model.set({'selected_field': this.model.get('fields').find(
                    function (f) {
                        return f.id === val;
                    })});

                // if selected field is blank, reset the summary Method
                if(!this.model.get('selected_field')) {
                    this.model.set({'summary_methods': 0});
                }
            }
        },

        initialize: function (options) {
            Backbone.View.prototype.initialize.apply(this, arguments);

            this.listenTo(this.model, 'change:fields', function () {
                this.render();
            });
        },

        render: function () {
            this.$('select#question')
                .empty()
                .html(this.template({
                    fields: this.model.get('fields').map(function (f) {
                        return {id: f.id, label: f.get('name')}
                    })
                }));
        }
    });

    Ona.SummaryMethodView = Backbone.View.extend({
        events: {
            'change input[type=checkbox]': function (evt) {
                var $target = $(evt.currentTarget);
                this.setSummaryMethods($target.val(), $target.prop('checked'));
            }
        },

        setSummaryMethods: function (value, setBit) {
            var val = parseInt(value),
                currentValue = this.model.get('summary_methods');
            if(setBit) {
                val = currentValue | val;
            } else {
                val = currentValue ^ val;
            }
            this.model.set({summary_methods: val});
        },

        initialize: function (options) {
            Backbone.View.prototype.initialize.apply(this, arguments);

            this.listenTo(this.model, 'change:selected_field', function () {
                this.render();
            })
        },

        render: function () {
            var self = this,
                selectedField = this.model.get('selected_field');

            // check the models `selected_field` to determine if we should enable our checkboxes
            var disabled = (selectedField || void 0) === void 0;
            _.each(['frequencies', 'percentages'], function (method) {
                var checked = (Ona.SummaryMethod[method.toUpperCase()] & self.model.get('summary_methods')) !== 0;
                self.$('.controls #' + method).prop('disabled', disabled);
                self.$('.controls #' + method).prop('checked', checked);
            });

            disabled = (selectedField || void 0) === void 0 || (selectedField && (selectedField.get('type') !== 'integer' && selectedField.get('type') !== 'decimal'));
            _.each(['mean', 'median', 'mode'], function (method) {
                var checked = (Ona.SummaryMethod[method.toUpperCase()] & self.model.get('summary_methods')) !== 0;
                self.$('.controls #' + method).prop('disabled', disabled);
                self.$('.controls #' + method).prop('checked', checked);
            });
        }
    });

    Ona.LanguageModeView = Backbone.View.extend({
        template: _.template('' +
            '<label class="radio">' +
              '<input type="radio" name="display_language" value="-1" <% if("-1" === selected_language) { %>checked="checked"<% } %> />' +
            'Show XML Values</label>' +
            '<% _.each(languages, function (lang) { %>' +
              '<label class="radio">' +
                '<input type="radio" name="display_language" value="<%= lang["name"] %>" <% if(lang["name"] === selected_language) { %>checked="checked"<% } %> />' +
              'Show in <%= lang["label"] %></label>' +
            '<% }) %>'),

        events: {
            'change input[type=radio]': function (evt) {
                var $target = Backbone.$(evt.currentTarget);
                this.model.set({selected_language: $target.val() || void 0});
            }
        },

        initialize: function (options) {
            Backbone.View.prototype.initialize.apply(this, arguments);

            this.listenTo(this.model, 'change:languages', function () {
                this.render();
            })
        },

        render: function () {
            // if languages.length is 0, add a default language as `Show Labels`
            var languages = [];
            if(this.model.get('languages').length === 0) {
                languages = [{name: '', label: "Show Labels"}]
            } else {
                languages = this.model.get('languages').map(function (lang) {
                    return {name: lang, label: lang}
                });
            }
            this.$('.controls')
                .empty()
                .html(this.template({
                    languages: languages,
                    selected_language: this.model.get('selected_language')
                }));
            return this;
        }
    });

    Ona.StatsCollection = Backbone.Collection.extend({
        initialize: function (models, options) {
            Backbone.Collection.prototype.initialize.apply(this, arguments);

            this.url = options.url;
            this.field = options.field;
            this.summaryMethods = options.summaryMethods || 0;
        },

        parse: function(response) {
            var data = [],
                field_name = this.field.id,
                self = this;

            _.each(response[field_name], function(val, key) {
                // Check if this summary method is enabled
                if(self.summaryMethods & Ona.SummaryMethod[key.toUpperCase()]) {
                    data.push({stat: key, value: val});
                }
            });
            return data;
        }
    });

    Ona.StatsCollection.StatsSummariesEnabled = function (summaryMethods) {
        return (summaryMethods & Ona.SummaryMethod.MEAN) !== 0 ||
            (summaryMethods & Ona.SummaryMethod.MEDIAN) !== 0 ||
            (summaryMethods & Ona.SummaryMethod.MODE) !== 0;
    };

    Ona.FrequenciesCollection = Backbone.Collection.extend({
        initialize: function (models, options) {
            Backbone.Collection.prototype.initialize.apply(this, arguments);

            this.baseUrl = options.baseUrl;
            this.field = options.field;
            this.summaryMethods = options.summaryMethods || 0;
            this.selectedLanguage = options.selectedLanguage;
        },

        url: function () {
            return this.baseUrl + '?group=' + this.field.id;
        },

        parse: function(response) {
            var self = this,
                sum = _.reduce(
                _.map(
                    response, function(o){
                        return o.count || 0;
                    }), function(memo, val){
                    return memo + val;
                });

            // Calculate percentages
            return _.map(response, function (obj) {
                var objWithPercentage = {count: obj.count, percentage: (obj.count/sum) * 100};

                // if field is a select (one, multiple) get the values for the specified language
                if((self.field.isA(FH.types.SELECT_ONE) || self.field.isA(FH.types.SELECT_MULTIPLE))
                    && self.selectedLanguage !== '-1') {
                    objWithPercentage[self.field.id] = Ona.FrequenciesCollection.LabelsForSelect(obj[self.field.id], self.field, self.selectedLanguage);
                } else {
                    objWithPercentage[self.field.id] = obj[self.field.id];
                }
                // append a not specified if required
                if(!objWithPercentage[self.field.id]) {
                    objWithPercentage[self.field.id] = "-";
                }
                return objWithPercentage;
            });
        }
    });

    Ona.FrequenciesCollection.LabelsForSelect = function(value, field, language) {
        var selections,
            results = [],
            choices = new FH.FieldSet(field.get(FH.constants.CHILDREN));

        // Split the value on a space to get a list for multiple choices
        selections = value && value.split(' ') || [];

        _.each(selections, function (selection) {
            var choice = choices.find(function (c) {
                return c.get(FH.constants.NAME) === selection;
            });
            if (choice) {
                results.push(choice.get(FH.constants.LABEL, language));
            }
        });
        return results.join(', ');
    };

    Ona.SummaryView = Backbone.View.extend({
        className: 'summary-view',
        events: {
            'click button.close': function (evt) {
                this.remove();
            }
        },
        initialize: function (options) {
            var field = this.model.get('selected_field');

            Backbone.View.prototype.initialize.apply(this, arguments);

            // Do we use the XML value (if selected language is -1) or the language
            var selected_language = this.model.get('selected_language');
            var label = selected_language === '-1'?field.get('name'):field.get('label', selected_language);

            var frequenciesCollection = new Ona.FrequenciesCollection([], {
                baseUrl: options.submissionStatsUrl,
                field: field,
                summaryMethods: this.model.get('summary_methods'),
                selectedLanguage: selected_language
            });
            var frequencyColumns = [
                {name: field.get('name'), label: "Answers", editable: false, cell: "string"}
            ];
            if(this.model.get('summary_methods') & Ona.SummaryMethod.FREQUENCIES) {
                frequencyColumns.push({name: 'count', label: "Frequencies", editable: false, cell: "integer"});
            }
            if(this.model.get('summary_methods') & Ona.SummaryMethod.PERCENTAGES) {
                frequencyColumns.push({
                    name: 'percentage',
                    label: "Percentage of Total",
                    editable: false,
                    cell: "number"
                });
            }
            this.frequencyTable = new Backgrid.Grid({
                className: 'backgrid table table-striped table-hover table-bordered summary-table',
                columns: frequencyColumns,
                collection: frequenciesCollection
            });
            frequenciesCollection.fetch();


            var statsCollection = new Ona.StatsCollection([], {
                url: options.url,
                field: field,
                summaryMethods: this.model.get('summary_methods')
            });

            this.statsTable = new Backgrid.Grid({
                className: 'backgrid table table-striped table-hover table-bordered stats-table',
                columns: [
                    {name: 'stat', label: "Statistic", editable: false, cell: "string"},
                    {name: 'value', label: "Value", editable: false, cell: "number"}
                ],
                collection: statsCollection
            });
            statsCollection.fetch();
        },

        render: function () {
            var field = this.model.get('selected_field'),
                selected_language = this.model.get('selected_language'),
                label = selected_language === '-1'?field.get('name'):field.get('label', selected_language);

            this.$el.empty()
                .append('<h3>'+ label +'<button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button></h3>');

            // show frequency table only if wither frequency or percentages is enabled
            if(this.model.get('summary_methods') & Ona.SummaryMethod.FREQUENCIES ||
                this.model.get('summary_methods') & Ona.SummaryMethod.PERCENTAGES) {
                this.$el
                    .append('<h4>' + "Frequency" +'</h3>')
                    .append(this.frequencyTable.render().$el);
            }

            // If field is numeric or we have one of the summary methods enabled, render the stats view as well
            if(fieldIsNumeric(this.model.get('selected_field')) &&
                Ona.StatsCollection.StatsSummariesEnabled(this.model.get('summary_methods'))) {
                this.$el
                    .append('<h4>' + "Statistics" +'</h3>')
                    .append(this.statsTable.render().$el);
            }
            return this;
        }
    });

    Ona.TableBuilderView = Backbone.View.extend({
        questionView: void 0,

        summaryMethodView: void 0,

        languageModeView: void 0,

        events: {
            'click button#create': function (evt) {
                var statsTable = new Ona.SummaryView({
                    submissionStatsUrl: this.submissionStatsUrl,
                    url: this.statsUrl,
                    model: new Backbone.Model({
                        selected_field: this.model.get('selected_field'),
                        summary_methods: this.model.get('summary_methods'),
                        selected_language: this.model.get('selected_language')
                    })
                });
                this.$statsEl.append(statsTable.render().$el);
            }
        },

        initialize: function (options) {
            Backbone.View.prototype.initialize.apply(this, arguments);

            this.$statsEl = Backbone.$(options.statsEl);
            this.$createButton = Backbone.$(options.createButtonSelector);
            this.submissionStatsUrl = options.submissionStatsUrl;
            this.statsUrl = options.statsUrl;

            // make sure we have a model
            this.model = new Backbone.Model({
                fields: new Backbone.Collection(),
                selected_field: void 0,
                summary_methods: 0,
                languages: [],
                selected_language: '-1'
            });

            // load the form
            this.form = new FH.Form({}, {
                url: options.formUrl
            });

            // on load, set our model's fields attribute
            this.form.on('sync', function (model, response, options) {
                this.model.set({fields: model.fields}),
                this.model.set({languages: model.get('languages')})
            }, this);

            // when `fields` change reset `selected_fields` and `summary_methods`
            this.model.on('change:fields', function () {
                this.model.set({
                    selected_field: void 0,
                    summary_methods: 0
                });
            }, this);

            // when `languages` change reset `selected_language`
            this.model.on('change:languages', function () {
                this.model.set({
                    selected_language: '-1'
                });
            }, this);

            // whenever any of `selected_field` or `summary_methods` change, check if we need to enable the button
            this.listenTo(this.model, 'change:selected_field', function (model, value, options) {
                var disabled = this.shouldDisableButton(model);
                this.$createButton.prop('disabled', disabled);

                // reset summary_methods
                this.model.set({summary_methods: 0});
            });

            // whenever any of `selected_field` or `summary_methods` change, check if we need to enable the button
            this.listenTo(this.model, 'change:summary_methods', function (model, value, options) {
                var disabled = Ona.TableBuilderView.ShouldDisableButton(model);
                this.$createButton.prop('disabled', disabled);
            });

            this.form.load();

            this.questionView = new Ona.QuestionView({
                el: this.$('#step-1'),
                model: this.model
            });

            this.summaryMethodView = new Ona.SummaryMethodView({
                el: this.$('#step-2'),
                model: this.model
            });

            this.languageModeView = new Ona.LanguageModeView({
                el: this.$('#step-3'),
                model: this.model
            });
        },

        render: function () {
            this.questionView.render();
            this.summaryMethodView.render();
            this.languageModeView.render();
            return this;
        }
    });

    Ona.TableBuilderView.ShouldDisableButton = function (model) {
        return !model.get('selected_field') || model.get('summary_methods') === 0;
    }
}).call(this)
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
            }
        },

        initialize: function (options) {
            Backbone.View.prototype.initialize.apply(this, arguments);

            this.listenTo(this.model, 'change:fields', function () {
                this.render();
            });

            this.listenTo(this.model, 'change:selected_field', function () {
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
            _.each(['frequencies', 'percentages'], function (method){
                self.$('.controls #' + method).prop('disabled', disabled);
            });

            disabled = (selectedField || void 0) === void 0 || (selectedField && (selectedField.get('type') !== 'integer' && selectedField.get('type') !== 'decimal'));
            _.each(['mean', 'median', 'mode'], function (method){
                self.$('.controls #' + method).prop('disabled', disabled);
            });
        }
    });

    Ona.LanguageModeView = Backbone.View.extend({
        template: _.template('' +
            '<% _.each(languages, function (lang) { %>' +
              '<label class="radio">' +
                '<input type="radio" name="display_language" value="<%= lang["name"] %>" <% if(lang["name"] === selected_language) { %>checked="checked"<% } %> />' +
              '<%= lang["label"] %></label>' +
            '<% }) %>'),
        render: function () {
            this.$('.controls')
                .empty()
                .html(this.template({
                    languages: this.model.get('languages'),
                    selected_language: this.model.get('selected_language')
                }));
            return this;
        }
    });

    Ona.SummaryView = Backbone.View.extend({
        initialize: function (options) {
            Backbone.View.prototype.initialize.apply(this, arguments);

            this.frequencyTable = new Backgrid.Grid({
                className: 'backgrid table table-striped table-hover table-bordered summary-table',
                columns: [
                    {name: 'age', label: "Age", editable: false, cell: "string"},
                    {name: 'count', label: "Count", editable: false, cell: "integer"},
                    {name: 'percentage', label: "%", editable: false, cell: "integer"}
                ],
                collection: new Backbone.Collection([
                    {age: 5, count: 12, percentage: 28},
                    {age: 25, count: 31, percentage: 72}
                ])
            });

            this.statsTable = new Backgrid.Grid({
                className: 'backgrid table table-striped table-hover table-bordered stats-table',
                columns: [
                    {name: 'stat', label: "Statistic", editable: false, cell: "string"},
                    {name: 'value', label: "Value", editable: false, cell: "string"}
                ],
                collection: new Backbone.Collection([
                    {stat: "Mean", value: 12},
                    {stat: "Median", value: 31},
                    {stat: "Mode", value: 31}
                ])
            });
        },

        render: function () {
            this.$el
                .empty()
                .append('<h3>'+ "Age" +'</h3>')
                .append('<h4>' + "Frequency" +'</h3>')
                .append(this.frequencyTable.render().$el);
            if(true) {
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

                });
                this.$statsEl.append(statsTable.render().$el);
            }
        },

        initialize: function (options) {
            Backbone.View.prototype.initialize.apply(this, arguments);

            this.$statsEl = Backbone.$(options.statsEl);

            // load the form
            this.form = new FH.Form({}, {
                url: options.formUrl
            });

            // on load, set our model's fields attribute
            this.form.on('sync', function (model, response, options) {
                this.model.set({fields: model.fields})
            }, this);

            // when `fields` change reset `selected_fields` and `summary_method`
            this.model.on('change:fields', function () {
                this.model.set({
                    selected_field: void 0,
                    summary_methods: 0
                });
            }, this);

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

    var tableBuilder = new Ona.TableBuilderView({
        el: '#table-create-form',
        statsEl: '#stats-tables-container',
        formUrl: '/larryweya/forms/tutorial/form.json',
        model: new Backbone.Model({
            fields: new Backbone.Collection([
                /*{id: 'name', label: 'Your Name', type: 'text'},
                {id: 'age', label: 'How old are you?', type: 'integer'},
                {id: 'gender', label: 'Gender', type: 'select one'}*/
            ]),
            selected_field: void 0,
            summary_methods: 0,
            languages: [
                {name: '-1', label: "Show XML Values"},
                {name: '', label: "Show labels"}
            ],
            selected_language: '-1'
        })
    });

    tableBuilder.render();
}).call(this)
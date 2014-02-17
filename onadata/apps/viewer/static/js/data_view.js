(function () {
    "use strict";
    // Save a reference to the global object (`window` in the browser, `exports`
    // on the server).
    var root = this;

    // Check if the `FH` namespace already exists and create it otherwise. We'll
    // attach all our exposed objects to it.
    var FH = root.FH = root.FH || {};

    // Map of FH types to Backgrid cell types
    var FHToBackgridTypes = {
        'integer': 'integer',
        'decimal': 'number',
        /*'select': '',
         'select all that apply': '',
         'select one': '',*/
        'photo': '',
        'image': '',
        'date': 'date',
        'datetime': 'datetime'
    };

    var PageableDataset = FH.PageableDataset = Backbone.PageableCollection.extend({
        state: {
            pageSize: 50
        },
        mode: "client", // page entirely on the client side,
        model: FH.Data,
        initialize: function (models, options) {
            // set the url
            /*if(! options.url) {
             throw new Error(
             "You must specify the dataset's url within the options");
             }*/
            this.url = options && options.url;

            // Call super
            return Backbone.PageableCollection.prototype.initialize.apply(this, arguments);
        }
    });

    var NameLabelToggle = Backbone.View.extend({
        className: 'table-control-container label-toggle-container',

        template: _.template('' +
            '<span>' +
            '<label class="checkbox">' +
            '<input class="name-label-toggle" type="checkbox" name="toggle_labels" aria-controls="data-table" <% if (isChecked) { %>checked="checked" <% } %> />' +
            ' Toggle between choice names and choice labels' +
            '</label>' +
            '</span>'),

        events: {
            'click .name-label-toggle': "toggleLabels"
        },

        render: function () {
            this.$el.empty().append(this.template({
                isChecked: false
            }));
            this.delegateEvents();
            return this;
        },

        toggleLabels: function (e) {
            var enabled = !!$(e.currentTarget).attr('checked');
            this.trigger('toggled', enabled);
        }
    });

    var ClickableRow = Backgrid.Row.extend({
        highlightColor: 'lightYellow',
        events: {
            'dblclick': 'rowDoubleClicked'
        },
        initialize: function (options) {
            return Backgrid.Row.prototype.initialize.apply(this, arguments);
        },
        rowDoubleClicked: function (evt) {
            var record_id = this.model.get("_id");
            if (record_id) {
                window.open(instance_view_url + "#/" + record_id, "_blank");
            }
        }
    });

    var DataTableView = FH.DataTableView = Backbone.View.extend({
        // Instance of the `Form` object
        form: void 0,

        // Instance of the `Data` object
        data: void 0,

        // Whether to show header names or labels
        showHeaderLabels: false,

        // Whether to show select names or labels
        showLabels: false,

        initialize: function (options) {
            if (!options.formUrl) {
                throw new Error("You must define a formUrl property within options");
            }

            if (!options.dataUrl) {
                throw new Error("You must define a dataUrl property within options");
            }

            // Setup the form
            this.form = new FH.Form({}, {url: options.formUrl});

            // Setup the data
            this.data = new FH.PageableDataset([], {
                url: options.dataUrl
            });

            // Initialize the header name/label toggle
            var headerLangSwitcher = new NameLabelLanguagePicker({
                label: "Column Headers",
                model: this.form
            });

            // Initialize the data name/label toggle
            var dataLangSwitcher = new NameLabelLanguagePicker({
                label: "Answer Values",
                model: this.form
            });

            this.form.on('load', function () {
                var dataTableView = this;

                // Initialize the data
                this.data.on('load', function () {

                    // Disable this callback - infinite loop
                    this.data.off('load');

                    // Append the toggle labels checkbox
                    $(this.labelToggleTemplate({isChecked: this.showLabels})).insertAfter(this.$('.dynatable-per-page'));

                    this.delegateEvents({
                        'click input.toggle-labels': 'onToggleLabels'
                    });
                }, this);

                // Initialize the grid
                this.dataGrid = new Backgrid.Grid({
                    row: ClickableRow,
                    className: 'backgrid table table-striped table-hover',
                    columns: this.form.fields.map(function (f) {
                        var column = {
                            name: f.get(FH.constants.XPATH),
                            label: f.get(FH.constants.NAME),
                            editable: false,
                            cell: "string"//FHToBackgridTypes[f.get(FH.constants.TYPE)] || "string"
                        };
                        if (f.isA(FH.types.SELECT_ONE) || f.isA(FH.types.SELECT_MULTIPLE)) {
                            column.formatter = {
                                fromRaw: function (rawData) {
                                    return DataTableView.NameOrLabel(f, rawData, dataTableView.showLabels, dataTableView.form.get('language'));
                                }
                            };
                        }
                        if (f.isA(FH.types.INTEGER) || f.isA(FH.types.DECIMAL)) {
                            column.sortValue = function (model, fieldId) {
                                var func = FH.ParseFunctionMapping[f.get(FH.constants.TYPE)];
                                return FH.DataSet.GetSortValue(model, fieldId, func);
                            }
                        }
                        return column;
                    }),
                    collection: this.data
                });

                this.$el.append(this.dataGrid.render().$el);

                // Initialize the paginator
                var paginator = new Backgrid.Extension.Paginator({
                    collection: this.data
                });

                // Render the paginator
                this.$el.append(paginator.render().$el);

                // Initialize a client-side filter to filter on the client
                // mode pageable collection's cache.
                var filter = new Backgrid.Extension.ClientSideFilter({
                    collection: this.data.fullCollection
                });

                // Render the filter
                this.$el.prepend(filter.render().$el);

                // Add some space to the filter and move it to the right
                filter.$el.css({float: "right", margin: "20px"});

                // catch the `switched` event
                dataLangSwitcher.on('switch', function (language) {
                    // if the new language is `0`, we want to show xml values, otherwise, we want labels in whatever language is specified
                    this.showLabels = language !== '-1';
                    // set the language if we're showing labels
                    if (this.showLabels) {
                        this.form.set({language: language}, {silent: true});
                    }
                    this.dataGrid.render();
                }, this);

                this.$el.prepend(dataLangSwitcher.render().$el);

                // catch the `switched` event
                headerLangSwitcher.on('switch', function (language) {
                    // if the new language is `0`, we want to show xml values, otherwise, we want labels in whatever language is specified
                    this.showHeaderLabels = language !== '-1';
                    // set the language if we're showing labels
                    this.form.set({header_language: language});
                }, this);

                this.$el.prepend(headerLangSwitcher.render().$el);

                // only add the language picker if we have multiple languages
                if (this.form.get('languages') && this.form.get('languages').length > 1) {
                    // Initialize the language selector
                    var languagePicker = new FH.LanguagePicker({
                        model: this.form,
                        className: 'table-control-container language-picker-container'
                    });

                    languagePicker.render().$el.insertBefore(this.$('.label-toggle-container'));
                }

                // Fetch some data
                this.data.fetch({reset: true});

            }, this);

            // Catch language change events
            this.form.on('change:header_language', function (model, language) {
                var dataTableView = this;
                if (this.dataGrid) {
                    this.dataGrid.columns.each(function (column) {
                        var label,
                            field = dataTableView.form.fields
                                .find(function (f) {
                                    return f.get(FH.constants.XPATH) === column.get('name');
                                });

                        if (dataTableView.showHeaderLabels) {
                            label = field.get(FH.constants.LABEL, language);
                        } else {
                            label = field.get(FH.constants.NAME);
                        }
                        column.set({'label': label});
                    });
                    this.dataGrid.header.render();
                }
            }, this);

            this.form.load();
        }
    });

    var NameLabelLanguagePicker = Backbone.View.extend({
        label: void 0,

        className: 'table-control-container',

        template: _.template(
            '<label><%= label %></label><select><% _.each(languages, function(lang){ %>' +
                '<option value="<%= lang["name"] %>"><%= lang["value"] %></option> ' +
            '<% }); %></select>'),

        events: {
            'change select': function (evt) {
                var value = $(evt.currentTarget).val() || undefined;
                this.trigger('switch', value);
            }
        },

        initialize: function (options) {
            this.label = options.label || "&nbsp;";
            Backbone.View.prototype.initialize.apply(this, arguments);
        },

        render: function () {
            var languages = NameLabelLanguagePicker.LanguagesForSelect(
                this.model);
            this.$el.empty().append(this.template({
                languages: languages,
                label: this.label
            }));
            return this;
        }
    });

    NameLabelLanguagePicker.LanguagesForSelect = function (model) {
        var languages = model.get('languages').length == 0?
            [{name: null, value: 'Show Labels'}]:
            model.get('languages').map(
                function(lang){
                    return {name: lang, value: "Show Labels in " + lang};
                });
        languages.unshift({name: '-1', value: 'Show XML Values'});
        return languages
    };

    // Used by select formatters to return wither name the name or label for a response
    DataTableView.NameOrLabel = function (field, value, showLabels, language) {
        var xpath,
            choices,
            selections,
            results;

        // if showLabels === true, get the label for the selected value(s)
        if (showLabels) {
            choices = new FH.FieldSet(field.get(FH.constants.CHILDREN));

            // Split the value on a space to get a list for multiple choices
            selections = value && value.split(' ') || [];
            results = [];

            _.each(selections, function (selection) {
                var choice = choices.find(function (c) {
                    return c.get(FH.constants.NAME) === selection;
                });
                if (choice) {
                    results.push(choice.get(FH.constants.LABEL, language));
                }
            });
            return results.join(', ');
        } else {
            return value;
        }
    };
}).call(this);

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
            pageSize: 15
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

    var DataView = FH.DataView = Backbone.View.extend({
        // Instance of the `Form` object
        form: void 0,

        // Instance of the `Data` object
        data: void 0,

        // Table header template
        headerTemplate: _.template('' +
            '<tr>' +
            '<% _.each(columns, function (column){ %>' +
            '<th><%= column %></th>' +
            '<% }); %>' +
            '</tr>'),

        // toggle label template
        labelToggleTemplate: _.template('' +
            '<span>' +
            '<label>' +
            '<input class="toggle-labels" type="checkbox" name="toggle_labels" aria-controls="data-table" <% if (isChecked) { %>checked="checked" <% } %> />' +
            ' Show select labels' +
            '</label>' +
            '</span>'),

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
                url: options.dataUrl,
                state: {
                    pageSize: 5
                }
            });

            this.form.on('load', function () {
                // Render the columns
                /*this.$('table thead')
                    .empty()
                    .append(this.headerTemplate({
                        columns: this.form.fields.map(function (field) {
                            return field.get(FH.constants.LABEL);
                        })
                    }));*/

                // Initialize the data
                this.data.on('load', function () {
                    var dataView = this;

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
                    columns: this.form.fields.map(function (f) {
                        return {
                            name: f.get(FH.constants.XPATH),
                            label: f.get(FH.constants.LABEL),
                            editable: false,
                            cell: "string"//FHToBackgridTypes[f.get(FH.constants.TYPE)] || "string"
                        };
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
                    collection: this.data,
                    fields: ['name']
                });

                // Render the filter
                this.$el.prepend(filter.render().$el);

                // Add some space to the filter and move it to the right
                filter.$el.css({float: "right", margin: "20px"});

                // Fetch some data
                this.data.fetch({reset: true});

            }, this);
            this.form.load();
        },

        onToggleLabels: function (evt) {
            var target = evt.currentTarget;
            if (target.checked) {
                this.showLabels = true;
            } else {
                this.showLabels = false;
            }
            this.dynatable.dom.update();
        }
    });

    DataView.dataTableColumns = function (form) {
        var dataView = this;
        return form.fields.map(function (field) {
            var funcOrNull,
                cleanedXPath = field.get(FH.constants.XPATH).replace(/\./g, "-");

            if (FH.Field.isA(field.get(FH.constants.TYPE), FH.types.SELECT_ONE) ||
                FH.Field.isA(field.get(FH.constants.TYPE), FH.types.SELECT_MULTIPLE)) {
                funcOrNull = DataView.NameOrLabel.call(dataView, field);
            } else {
                funcOrNull = cleanedXPath;
            }
            return {
                // Replace dots with dashes, datatables dont like them dots
                // If the field is a select, use a function to
                mData: funcOrNull,
                //mRender: funcOrNull,
                sTitle: field.get(FH.constants.LABEL)
            };
        });
    };

    // Called by dataTables to retrieve a value for a select column,
    // we determine whether to use the name or label here
    DataView.NameOrLabel = function (field, data) {
        var dataView = this,
            xpath,
            choices,
            selections,
            results,
            response;

        // if showLabels === true, get the label for the selected value(s)
        if (dataView.showLabels) {
            xpath = field.get(FH.constants.XPATH);//.replace(/\./g, '-');
            choices = new FH.FieldSet(field.get(FH.constants.CHILDREN));

            // get the value from the data
            response = data && data[xpath] || null;

            // Split the value on a space to get a list for multiple choices
            selections = response && response.split(' ') || [];
            results = [];

            _.each(selections, function (selection) {
                var choice = choices.find(function (c) {
                    return c.get(FH.constants.NAME) === selection;
                });
                if (choice) {
                    results.push(choice.get(FH.constants.LABEL));
                }
            });
            return results.join(', ');
        } else {
            return data && data[field.get(FH.constants.XPATH)] || null;
        }
    };

    DataView.dataSetToDataTables = function (form, dataSet) {
        // For each column, set the value or undefined
        return dataSet.map(function (row) {
            var data = row.toJSON();

            // for each column, replace dots with dashes
            _.each(data, function (v, k) {
                if (k.match(/\./g)) {
                    data[k.replace(/\./g, '-')] = v;
                    delete(data[k]);
                }
            });

            form.fields.each(function (f) {
                var cleanedXPath = f.get(FH.constants.XPATH).replace(/\./g, "-");
                data[cleanedXPath] = data[cleanedXPath] || null;
            });
            return data;
        });
    };
}).call(this);

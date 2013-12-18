(function () {
    "use strict";
    // Save a reference to the global object (`window` in the browser, `exports`
    // on the server).
    var root = this;

    // Check if the `FH` namespace already exists and create it otherwise. We'll
    // attach all our exposed objects to it.
    var FH = root.FH = root.FH || {};

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
            '<span style="float: left">' +
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
            this.data = new FH.DataSet([], {url: options.dataUrl});

            this.form.on('load', function () {
                // Render the columns
                this.$('table thead')
                    .empty()
                    .append(this.headerTemplate({
                        columns: this.form.fields.map(function (field) {
                            return field.get(FH.constants.LABEL);
                        })
                    }));

                // Initialize the data
                this.data.on('load', function () {
                    var dataView = this;

                    // Disable this callback - infinite loop
                    this.data.off('load');

                    // For each column, append some data
                    // Initialize the data table with our columns
                    this.$('table')
                        .bind('dynatable:init', function(e, dynatable) {
                            dataView.dynatable = dynatable;
                        })
                        .dynatable({
                            table: {
                                defaultColumnIdStyle: function (fieldSet) {
                                    return function (label) {
                                        var field = fieldSet.find(function (field) {
                                            return field.get(FH.constants.LABEL) === label;
                                        });
                                        return field && field.get(FH.constants.XPATH) || label;
                                    };
                                }(this.form.fields)
                            },
                            dataset: {
                                records: this.data.toJSON()
                            },
                            writers: {
                                _attributeWriter: function (fieldSet) {
                                    return function (record) {
                                        var column = this;

                                        // Get the target field
                                        var field = fieldSet.find(function (field) {
                                            return field.get(FH.constants.XPATH) === column.id;
                                        });

                                        if(FH.Field.isA(field.get(FH.constants.TYPE), FH.types.SELECT_ONE) ||
                                            FH.Field.isA(field.get(FH.constants.TYPE), FH.types.SELECT_MULTIPLE)) {
                                            return field && DataView.NameOrLabel.call(dataView, field, record) || record[this.id] || "";
                                        } else {
                                            return record[this.id] && record[this.id] || "";
                                        }
                                    };
                                }(this.form.fields)
                            }
                        });

                    // Append the toggle labels checkbox
                    $(this.labelToggleTemplate({isChecked: this.showLabels})).insertAfter(this.$('.dynatable-per-page'));

                    this.delegateEvents({
                        'click input.toggle-labels': 'onToggleLabels'
                    });
                }, this);
                this.data.load();
            }, this);
            this.form.load();
        },

        onToggleLabels: function (evt) {
            var target = evt.currentTarget;
            if(target.checked) {
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

            if(FH.Field.isA(field.get(FH.constants.TYPE), FH.types.SELECT_ONE) ||
                FH.Field.isA(field.get(FH.constants.TYPE), FH.types.SELECT_MULTIPLE))
            {
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
                if(k.match(/\./g)) {
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

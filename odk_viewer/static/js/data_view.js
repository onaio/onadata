(function () {
    "use strict";
    // Save a reference to the global object (`window` in the browser, `exports`
    // on the server).
    var root = this;

    var DataView = root.DataView = Backbone.View.extend({
        // Instance of the `Form` object
        form: void 0,

        // Instance of the `Data` object
        data: void 0,

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
                // Initialize the data
                this.data.on('load', function () {
                    // Disable this callback - infinite loop
                    this.data.off('load');

                    // For each column, append some data
                    // Initialize the data table with our columns
                    this.$el.dataTable({
                        sScrollX: "100%",
                        //sScrollXInner: "110%",
                        aoColumns: DataView.dataTableColumns(this.form),
                        aaData: DataView.dataSetToDataTables(this.form, this.data)
                    });
                }, this);
                this.data.load();
            }, this);
            this.form.load();
        }
    });

    DataView.dataTableColumns = function (form) {
        return form.fields.map(function (field) {
            return {
                // Replace dots with dashes, datatables dont like dots
                mDataProp: field.get(FH.constants.XPATH).replace(/\./g, "-"),
                sTitle: field.get(FH.constants.LABEL)
            };
        });
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
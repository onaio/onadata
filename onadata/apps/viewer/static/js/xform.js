// FH.Form Closure
// ------------------
(function(){
    "use strict";
    // Save a reference to the global object (`window` in the browser, `exports`
    // on the server).
    var root = this;

    // Check if the `FH` namespace already exists and create it otherwise. We'll
    // attach all our exposed objects to it.
    var FH = root.FH = root.FH || {};

    FH.constants = {
        ID_STRING: 'id_string',
        NAME: 'name',
        XPATH: 'xpath',
        LABEL: 'label',
        CHILDREN: 'children',
        GROUP: 'group',
        NOTE: 'note',
        XFORM_ID_STRING: '_xform_id_string',
        TYPE: 'type'
    };

    FH.types = {
        TEXT: ['text'],
        INTEGER: ['integer'],
        DECIMAL: ['decimal'],
        GEOLOCATION: ['gps', 'geopoint'],
        SELECT_ONE: ['select one', 'select_one'],
        SELECT_MULTIPLE: ['select', 'select all that apply'],
        PHOTO: ['photo', 'image']
    };

    FH.ParseFunctionMapping = {};
    FH.ParseFunctionMapping[FH.types.INTEGER] = parseInt;
    FH.ParseFunctionMapping[FH.types.INTEGER] = parseFloat;

    // #### A form's field
    var Field = FH.Field = Backbone.Model.extend({
        idAttribute: 'xpath',

        // Override `get` to handle requests for fields without labels e.g.
        // start and requests for multi-lingual labels
        get: function (key, language) {
            var val = Backbone.Model.prototype.get.apply(this, arguments);
            if(key === FH.constants.LABEL) {
                if(typeof val === typeof undefined) {
                    // Use the name as the label
                    val = Backbone.Model.prototype.get.call(this, FH.constants.NAME);
                } else if (typeof val === 'object') {
                    // If the language is specified, return its label, otherwise, return the first label
                    if(language) {
                        val = val[language];
                    } else {
                        throw new Error("You must specify a language");
                    }
                }
            }
            return val;
        },

        isA: function (typeConstant) {
            return typeConstant.indexOf(this.get(FH.constants.TYPE).toLowerCase()) !== -1;
        }
    });

    // Get the list of languages from a label
    FH.Field.languagesFromLabel = function(label) {
        if(typeof label === "string" || typeof label === "undefined") {
            return [];
        } else if (typeof label === "object") {
            return _.keys(label);
        } else {
            throw new Error("Don know how to handle label of type: " + typeof label);
        }
    };

    // Check if a field type string is a certain FH.type constant
    // e.g. FH.Field.isA('select one', FH.types.SELECT_ONE)
    FH.Field.isA = function (typeName, typeConstant) {
        return typeConstant.indexOf(typeName.toLowerCase()) !== -1;
    };

    // #### A collection of fields
    var FieldSet = FH.FieldSet = Backbone.Collection.extend({
      model: Field
    });

    // #### Form Wrapper
    // Pass in the form's url within options on initialisation
    // ```javascript
    // var form = new Form({}, {url: "http://formhub.org/user/forms/test/form.json"});
    // ```
    var Form = FH.Form = Backbone.Model.extend({
        fields: void 0,

        // Explicitly set url from option.url, newer Backbone doesnt
        initialize: function (attributes, options) {
            if(!options.url) {
                throw new Error("You must specify the form's url within the options");
            }
            this.url = options.url;

            // Initialize the `FieldSet`
            this.fields = new FieldSet();
        },

        // Override `set` to parse questions on load/set
        set: function (attributes, options) {
            var _that = this,
                languages = [],
                questions;

            // Check if we have children
            if(attributes[FH.constants.CHILDREN]) {
                questions = Form.parseQuestions(
                    attributes[FH.constants.CHILDREN]);

                questions.forEach(function (q) {
                    FH.Field.languagesFromLabel(q.label).forEach(function (lang) {
                        if (languages.indexOf(lang) === -1) {
                            languages.push(lang);
                        }
                    });
                    _that.fields.add(new Field(q));
                });

                // Set languages
                this.set({'languages': languages});

                // Set the current data language
                this.set({'language': languages[0]});

                // set current header language
                this.set({'header_language': '-1'});
            }

            // Check if we're setting children and parse fields
            return Backbone.Model.prototype.set.apply(this, arguments);
        },

        load: function () {
            var _that = this,
                xhr;

            xhr = this.fetch();
            xhr.done(function(){
                // trigger the `load` event
                _that.trigger('load');
            });
            xhr.fail(function(){
            });
        },

        questionsByType: function (fh_types) {
            return this.fields.filter(function(f){
                return _.indexOf(fh_types, f.get('type').toLowerCase()) !== -1;
            });
        }
    });

    // Pass in the top level `children` property from a form.json structure,
    // returns flat list of questions from all levels, discarding groups and
    // notes.
    FH.Form.parseQuestions = function (children, xpaths) {
        var questions = [];

        // The `xpaths` params is an empty list initially but is incrementally
        // built with every nested children group
        xpaths = xpaths || [];

        children.forEach( function (q) {
            if(q.type.toLowerCase() === FH.constants.GROUP)
            {
                var grouped = FH.Form.parseQuestions(q.children, xpaths.concat([q.name]));
                grouped.forEach(function(child){
                   questions.push(child);
                });
            }
            else if(q.type.toLowerCase() !== FH.constants.NOTE)
            {
                // generate xpath and set as id
                q.xpath = xpaths.concat([q.name]).join('/');
                questions.push(q);
            }
        });
        return questions;
    };

    // A single form data row
    FH.Data = Backbone.Model.extend({
        idAttribute: '_id',

        // Need to override url method as we query by params
        url: function () {
            return this.collection.url + '?query={"_id":' + this.id +'}';
        },

        // Load data form the server if necessary
        load: function () {
            var _that = this;

            // we hackily check if _xform_id_string is available as an
            // indication that all the data is available
            if(!this.get(FH.constants.XFORM_ID_STRING)) {
                this.fetch()
                    .done(function () {
                        _that.trigger('ready');
                    })
                    .fail(function () {
                        _that.trigger('readyFailed');
                    });
            } else {
                this.trigger('ready');
            }
        },

        // Data from the API is returned as an Array, we need to extract it
        parse: function (data) {
            // TODO: Hack for now, if data is an array, extract the first element
            if(_.isArray(data)) {
                data = data[0];
            }
            this.set(data);
        },

        // Override `sync` to use POST on delete
        sync: function (method, model, options) {
            if (method === 'delete') {
                method = 'create';
            }
            return Backbone.Model.prototype.sync.call(this, method, model, options);
        }
    });

    // A collection of form data
    FH.DataSet = Backbone.Collection.extend({
        model: FH.Data,
        initialize: function (models, options) {
            // set the url
            if(! options.url) {
                throw new Error(
                    "You must specify the dataset's url within the options");
            }
            this.url = options.url;
        },
        // Load data from the server, `params` can contain:
        // - query: An object of specifying the filter params for the query
        // - fields: a list of fieldnames to retrieve
        // - start: number of records to skip
        // - limit: number of records to limit
        // reset: whether to replace existing records or to merge
        load: function (params, reset) {
            var xhr,
                _that = this;

            params = params || {};
            reset = !!reset || false;

            // Stringify query params
            params.query && (params.query = JSON.stringify(params.query));
            params.fields && (params.fields = JSON.stringify(params.fields));
            params.start && (params.start = JSON.stringify(params.start));

            xhr = this.fetch({
                data: params,
                reset: reset
            });
            xhr.done(function () {
                _that.trigger('load', arguments);
            });
            xhr.fail(function () {
                console.error("Failed to load data.");
            });
        }
    });

    FH.DataSet.GetSortValue = function (model, fieldId, parseFunction) {
        var value = parseFunction(model.get(fieldId));
        return isNaN(value)?0:value;
    };

    // Encapsulates a DataSet and FieldSet within a `datavore` table
    FH.DatavoreWrapper = Backbone.Model.extend({
        // The datavore table
        table: void 0,

        // Initialise with a `fieldSet` and `dataSet` within `attributes`
        initialize: function (attributes, options) {
            // Column structure that we build and pass to the table
            var cols = [],
                dataSet = this.get('dataSet'),
                fieldSet = this.get('fieldSet');

            if( !dataSet || !fieldSet ) {
                throw new Error("You must specify the dataSet and the fieldSet");
            }

            // Build columns
            cols = fieldSet.map(function (field) {
                var xpath = field.get('xpath');
                if( !xpath ) {
                    throw new Error("Field '" + field.get('name') + "' doesnt have an xpath attribute");
                }

                return {
                    name: xpath,
                    values: [],
                    type: FH.DatavoreWrapper.fhToDatavoreType(field.get('type'))};
            });

            // Prepend the meta _id column
            cols.splice(0, 0, {name: '_id', values: [], type: dv.type.unknown});

            // Iterate over the records
            dataSet.each(function (record) {
                cols.forEach(function (col) {
                   col.values.push(record.get(col.name));
                });
            });
            this.table = dv.table(cols);
        },

        countBy: function (xpath) {
            var aggregation = this.table.query(
                {dims: [xpath], vals: [dv.count()]});
            return _.map(aggregation[0], function (item, idx) {
                return {key: item, value: aggregation[1][idx]};
            });
        }
    });

    // Converts FH types to one of the datavore types
    FH.DatavoreWrapper.fhToDatavoreType = function (typeName) {
        if( FH.Field.isA(typeName, FH.types.SELECT_ONE) ) {
            return dv.type.nominal;
        } else if (FH.Field.isA(typeName, FH.types.INTEGER) || FH.Field.isA(typeName, FH.types.DECIMAL) ) {
            return dv.type.numeric;
        } else {
            return dv.type.unknown;
        }
    };

    FH.LanguagePicker = Backbone.View.extend({
        languages: [],

        currentLang: void 0,

        template: _.template(
            '<select class="language-selector">' +
                '<% _.each(languages, function(lang){ %>' +
                '<option value="<%= lang %>" <% if(lang === currentLang){ %> selected="" <% } %>><%= lang %></option>' +
                '<% }); %>' +
            '</select>'),

        events: {
            'change .language-selector': 'languageChanged'
        },

        initialize: function (options) {
            Backbone.View.prototype.initialize.apply(this, arguments);
        },

        render: function () {
            this.$el.empty().append(this.template({
                languages: this.model.get('languages'),
                currentLang: this.model.get('language')
            }));
            return this;
        },

        languageChanged: function (e) {
            var language = $(e.currentTarget).val();
            this.model.set({'language': language});
        }
    });
}).call(this);

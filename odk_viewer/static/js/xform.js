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
        CHILDREN: 'children',
        GROUP: 'group',
        NOTE: 'note',
        XFORM_ID_STRING: '_xform_id_string'
    };

    FH.types = {
        GEOLOCATION: ['gps', 'geopoint'],
        SELECT_ONE: ['select one', 'select_one']
    };

    // #### A form's field
    var Field = FH.Field = Backbone.Model.extend({
        idAttribute: 'xpath'
    });

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
        load: function () {
            var fields = this.fields = new FieldSet(),
                this_form = this,
                xhr;

            xhr = this.fetch();
            xhr.done(function(){
                var questions = Form.parseQuestions(
                    this_form.get(FH.constants.CHILDREN));
                questions.forEach(function(q){
                    fields.add(new Field(q));
                });
                // trigger the `load` event
                this_form.trigger('load');
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
                _that.fetch()
                    .done(function () {
                        _that.trigger('ready');
                    })
                    .fail(function () {
                        _that.trigger('readyFailed');
                    });
            } else {
                _that.trigger('ready');
            }
        },

        // Data from the API is returned as an Array, we need to extract it
        parse: function (data) {
            // TODO: Hack for now, if data is an array, extract the first element
            if(_.isArray(data)) {
                data = data[0];
            }
            this.set(data);
        }
    });

    // #### DataSet
    // A collection for form data
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

            // String-ify query params
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
}).call(this);

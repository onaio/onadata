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
        CHILDREN: 'children',
        GROUP: 'group',
        NOTE: 'note'
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
        init: function(){
            var fields = new FieldSet(),
                this_form = this,
                xhr;
            this.fields = fields;

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

        questionsByType: function(fh_types){
            return this.fields.filter(function(f){
                return _.indexOf(fh_types, f.get('type').toLowerCase()) !== -1;
            });
        }
    });

    // #### Parse form.json questions
    // Pass in the top level `children` property from a form.json structure,
    // returns flat list of questions from all levels, discarding groups and
    // notes.
    FH.Form.parseQuestions = function(children, xpaths){
        var questions = [];

        // The `xpaths` params is an empty list initially but is incrementally
        // built with every nested children group
        xpaths = xpaths || [];

        children.forEach(function(q){
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

    FH.Data = Backbone.Model.extend({
        query: function(query, fields, start, limit){

        }
    });
}).call(this);

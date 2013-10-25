var FHField = Backbone.Model.extend({
    idAttribute: 'xpath'
});

var FHFieldSet = Backbone.Collection.extend({
  model: FHField
});

var FHForm = Backbone.Model.extend({
    init: function(){
        var fields = new FHFieldSet(),
            this_form = this,
            xhr;
        this.fields = fields;

        xhr = this.fetch();
        xhr.done(function(){
            var questions = FHForm.parseQuestions(this_form.get(FHForm.constants.CHILDREN));
            questions.forEach(function(q){
                fields.add(new FHField(q));
            });
            // trigger the **load** event
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

FHForm.constants = {
    ID_STRING: 'id_string',
    CHILDREN: 'children',
    GROUP: 'group',
    NOTE: 'note'
};

FHForm.types = {
    GEOLOCATION: ['gps', 'geopoint'],
    SELECT_ONE: ['select one', 'select_one']
};

FHForm.parseQuestions = function(children, xpaths){
    var questions = [];
    if(typeof xpaths === typeof undefined)
    {
        xpaths = [];
    }

    children.forEach(function(q){
        if(q.type.toLowerCase() === FHForm.constants.GROUP)
        {
            var grouped = FHForm.parseQuestions(q.children, xpaths.concat([q.name]));
            grouped.forEach(function(child){
               questions.push(child);
            });
        }
        else if(q.type.toLowerCase() !== FHForm.constants.NOTE)
        {
            // generate xpath and set as id
            q.xpath = xpaths.concat([q.name]).join('/');
            questions.push(q);
        }
    });
    return questions;
};

var FHData = Backbone.Model.extend({
    query: function(query, fields, start, limit){

    }
});

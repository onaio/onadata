var namespace,
  __slice = [].slice,
  __hasProp = {}.hasOwnProperty,
  __extends = function(child, parent) { for (var key in parent) { if (__hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; };

namespace = function(target, name, block) {
  var item, top, _i, _len, _ref, _ref1;
  if (arguments.length < 3) {
    _ref = [(typeof exports !== 'undefined' ? exports : window)].concat(__slice.call(arguments)), target = _ref[0], name = _ref[1], block = _ref[2];
  }
  top = target;
  _ref1 = name.split('.');
  for (_i = 0, _len = _ref1.length; _i < _len; _i++) {
    item = _ref1[_i];
    target = target[item] || (target[item] = {});
  }
  return block(target, top);
};

namespace('fh', function(exports) {
  exports.constants = {
    NAME: "name",
    LABEL: "label",
    TYPE: "type",
    CHILDREN: "children",
    TEXT: "text",
    INTEGER: "integer",
    DECIMAL: "decimal",
    SELECT_ONE: "select one",
    SELECT_MULTIPLE: "select multiple",
    GROUP: "group",
    HINT: "hint",
    GEOPOINT: "geopoint",
    _ID: "_id",
    START: "start",
    LIMIT: "limit",
    COUNT: "count",
    FIELDS: "fields",
    GEOLOCATION: "_geolocation",
    GEOFIELD: "geoField",
    FH_TYPE: "fhType"
  };
  return exports.Dataset = (function(_super) {

    __extends(Dataset, _super);

    function Dataset(options) {
      Dataset.__super__.constructor.call(this, options);
    }

    Dataset.prototype.fieldsByFhType = function(typeName) {
      var fields,
        _this = this;
      fields = this.fields.filter(function(field) {
        return field.get(fh.constants.FH_TYPE) === typeName;
      });
      return new recline.Model.FieldList(fields);
    };

    return Dataset;

  })(recline.Model.Dataset);
});

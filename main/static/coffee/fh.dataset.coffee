namespace = (target, name, block) ->
  [target, name, block] = [(if typeof exports isnt 'undefined' then exports else window), arguments...] if arguments.length < 3
  top    = target
  target = target[item] or= {} for item in name.split '.'
  block target, top

namespace 'fh', (exports) ->
  exports.constants = {
    # pyxform constants
    NAME: "name", LABEL: "label", TYPE: "type", CHILDREN: "children"
    # field types
    TEXT: "text", INTEGER: "integer", DECIMAL: "decimal", SELECT_ONE: "select one", SELECT_MULTIPLE: "select multiple",GROUP: "group", HINT: "hint", GEOPOINT: "geopoint",
    # formhub query syntax constants
    ID: "_id", START: "start", LIMIT: "limit", COUNT: "count", FIELDS: "fields",
    # others
    GEOLOCATION: "_geolocation", GEOFIELD: "geoField", FH_TYPE: "fhType"
  };

  class exports.Dataset extends recline.Model.Dataset
    constructor: (options) ->
      super options

    fieldsByFhType: (typeName) ->
      fields = @fields.filter (field) =>
        return field.get(fh.constants.FH_TYPE) is typeName
      return new recline.Model.FieldList(fields)
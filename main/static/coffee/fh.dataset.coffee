namespace = (target, name, block) ->
  [target, name, block] = [(if typeof exports isnt 'undefined' then exports else window), arguments...] if arguments.length < 3
  top    = target
  target = target[item] or= {} for item in name.split '.'
  block target, top

namespace 'fh', (exports) ->
  class exports.Dataset extends recline.Model.Dataset
    constructor: (options) ->
      super options

    fieldsByType: (typeName) ->
      fields = @fields.filter (field) =>
        return field.get('type') is typeName
      return new recline.Model.FieldList(fields)
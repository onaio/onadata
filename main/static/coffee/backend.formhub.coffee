namespace = (target, name, block) ->
  [target, name, block] = [(if typeof exports isnt 'undefined' then exports else window), arguments...] if arguments.length < 3
  top    = target
  target = target[item] or= {} for item in name.split '.'
  block target, top

namespace 'recline.Backend.Formhub', (exports) ->
  exports.__type__ = 'formhub';

  _parseSchema = (schema) ->
    metadata = {}
    fields = []
    parseFields = (fieldsDef) =>
      _.each fieldsDef, (fieldObject, index, list) ->
        if fieldObject.type isnt "group"
          fields.push({id: fieldObject.name, label: fieldObject.label ? null })
        else if fieldObject.type is exports.constants.GROUP and fieldObject.hasOwnProperty(exports.constants.CHILDREN)
          parseFields(fieldObject.children)
    _.each schema, (val, key) =>
      if key isnt "children"
        metadata[key] = val
    parseFields(schema.children)
    return {metadata: metadata, fields: fields}

  exports.fetch = (dataset) ->
    deferred = $.Deferred();
    jqXHR = $.getJSON(dataset.formurl)
    jqXHR.done (schema) ->
      # process fields
      schema = _parseSchema(schema)
      deferred.resolve({
        metadata: schema.metadata,
        fields: schema.fields
      })
    jqXHR.fail (e) ->
      deferred.reject(e)
    return deferred.promise()

  exports.query = (queryObj, dataset) ->
    deferred = $.Deferred();
    params = {start: queryObj.from, limit: queryObj.size}
    jqXHR = $.getJSON(dataset.dataurl, params)
    jqXHR.done (data) ->
      deferred.resolve({
        total: 22,
        hits: data
      })
    jqXHR.fail (e) ->
      deferred.reject(e)
    return deferred.promise()
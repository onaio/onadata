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
        if fieldObject.type isnt fh.constants.GROUP
          field = {id: fieldObject.name}
          # check for multi lang labels
          if fieldObject.label and typeof metadata.languages is "undefined"
            if typeof fieldObject.label is "object"
              metadata.languages = _.keys(fieldObject.label)
            else
              metadata.languages = ["default"]
          #field.label = (field) ->
          #  console.log(this)
          #  if fhlabels? && typeof fhlabels is "object"
          #    console.log(typeof fhlabels)
          #    return this.fhlabels["English"]
          #  else
          #    return this.fhlabels
          field.label = fieldObject.label ? null
          fields.push(field)
        else if fieldObject.type is exports.constants.GROUP and fieldObject.hasOwnProperty(exports.constants.CHILDREN)
          parseFields(fieldObject.children)

    _.each schema, (val, key) =>
      if key isnt fh.constants.CHILDREN
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
    # get the count
    params = {count: 1}
    jqXHR = $.getJSON(dataset.dataurl, params)
    jqXHR.done (data) ->
      total = data[0].count
      params = {start: queryObj.from, limit: queryObj.size}
      jqXHR = $.getJSON(dataset.dataurl, params)
      jqXHR.done (data) ->
        deferred.resolve({
          total: total,
          hits: data
        })
    jqXHR.fail (e) ->
      deferred.reject(e)
    return deferred.promise()
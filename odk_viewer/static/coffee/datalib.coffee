constants = {
  # pyxform constants
  NAME: "name", LABEL: "label", TYPE: "type", CHILDREN: "children", GROUP: "group", HINT: "hint", GEOPOINT: "geopoint"
  # formhub query syntax constants
  START: "start", LIMIT: "limit", COUNT: "count", FIELDS: "fields",
  # others
  GEOLOCATION: "_geolocation"
};
class Reader
  constructor: () ->

  read: (data) ->
    return data

class Loader
  constructor: (@_reader) ->

class MemoryLoader extends Loader
  constructor: (_reader, @_data) ->
    super(_reader)

  load: ->
    deferred = $.Deferred()

    if typeof @_data isnt "undefined" and @_data isnt null
      parsed_data = @_reader.read(@_data)
      deferred.resolve(parsed_data)
    else
      deferred.reject({"error": "No data available."});
    return deferred.promise()

class AjaxLoader extends Loader
  constructor: (_reader, @_url, @_params) ->
    super(_reader)

  load: ->
    deferred = $.Deferred()
    promise = $.get(@_url, @_params);
    promise.done (data) =>
      parsed_data = @_reader.read(data)
      deferred.resolve(parsed_data)
    promise.fail (e) =>
      deferred.reject(e)
    return deferred.promise();

class Field
  constructor: (fieldDef)->
    @_name = fieldDef.name
    @_type = fieldDef.type
    @_hint = if fieldDef.hasOwnProperty(constants.HINT) then fieldDef.hint else null
    @_label = if fieldDef.hasOwnProperty(constants.LABEL) then fieldDef.label else null
    @_options = []

    # check for choices
    if fieldDef.hasOwnProperty(constants.CHILDREN)
      _.each fieldDef.children, (val, key, list) =>
        @_options.push new Field(val)

  name: ->
    return @_name

  type: ->
    return @_type

  hint: ->
    return @_hint

  label: (language)->
    if typeof language isnt "undefined" and language isnt null
      return @_label[language]
    else
      # check if multi-lingual
      if typeof @_label is "object"
        # return first langauge
        return _.values(@_label)[0]
      else
        return @_label

  options: ->
    return @_options

class Manager
  init: (@_loader) ->
    promise = @_loader.load()
    promise.done (data) =>
      @onload(data)
    promise.fail (e) =>
      @onfail(e)
    return promise

  onload: (data) ->

  onfail: (e) ->

class SchemaManager extends Manager
  constructor: ->
    @_fields = []
    @_properties = {}
    @_supportedLanguages = []

  _parseLanguages: (fieldsDef) ->
    field = _.find fieldsDef, (field) ->
      return field.hasOwnProperty(constants.LABEL)
    label = field.label
    @_supportedLanguages = if typeof label is "object" then _.keys(label) else ["default"]


  _parseFields: (fieldsDef) ->
    _.each fieldsDef, (val, key, list) =>
      if fieldsDef.type isnt constants.GROUP
        @_fields.push new Field(val)
      else if fieldsDef.type is constants.GROUP and fieldsDef.hasOwnProperty(constants.CHILDREN)
        @_parseFields(fieldsDef.children)

  _parseSchema: (schemaDef) ->
    _.each schemaDef, (val, key, list) =>
      if key isnt constants.CHILDREN
        @_properties[key] = val
      else
        @_parseLanguages(val)
        @_parseFields(val)

  # return top level formjson properties
  get: (property) ->
    return @_properties[property]

  onload: (data) ->
    @_parseSchema data

  getFieldByName: (name) ->
    _.find @_fields, (field) ->
      return field.name() is name

  getFieldsByType: (typeName) ->
    _.filter @_fields, (field) ->
      return field.type() is typeName

  getSupportedLanguages: ->
    return @_supportedLanguages


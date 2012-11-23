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
    GEOLOCATION: "_geolocation"
  };

  class exports.Reader
    constructor: () ->

    read: (data) ->
      return data

  class exports.Loader
    constructor: (@_reader) ->
      if typeof @_reader is "undefined" or @_reader is null
        @_reader = new exports.Reader()

  class exports.MemoryLoader extends exports.Loader
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

  class exports.AjaxLoader extends exports.Loader
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

  class exports.Field
    constructor: (fieldDef)->
      @_name = fieldDef.name
      @_setType(fieldDef.type)
      @_hint = if fieldDef.hasOwnProperty(exports.constants.HINT) then fieldDef.hint else null
      @_label = if fieldDef.hasOwnProperty(exports.constants.LABEL) then fieldDef.label else null
      @_options = []

      # check for choices
      if fieldDef.hasOwnProperty(exports.constants.CHILDREN)
        _.each fieldDef.children, (val, key, list) =>
          @_options.push new exports.Field(val)

    _setType: (typeName)->
      @_type = typeName

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

  class exports.Manager
    init: (@_loader) ->
      promise = @_loader.load()
      promise.done (data) =>
        @onload(data)
      promise.fail (e) =>
        @onfail(e)
      return promise

    onload: (data) ->

    onfail: (e) ->

  class exports.SchemaManager extends exports.Manager
    constructor: ->
      @_fields = []
      @_properties = {}
      @_supportedLanguages = []

    _parseLanguages: (fieldsDef) ->
      field = _.find fieldsDef, (field) ->
        return field.hasOwnProperty(exports.constants.LABEL)
      label = field.label
      @_supportedLanguages = if typeof label is "object" then _.keys(label) else ["default"]


    _parseFields: (fieldsDef) ->
      _.each fieldsDef, (fieldObject, index, list) =>
        if fieldObject.type isnt exports.constants.GROUP
          @_fields.push new exports.Field(fieldObject)
        else if fieldObject.type is exports.constants.GROUP and fieldObject.hasOwnProperty(exports.constants.CHILDREN)
          @_parseFields(fieldObject.children)

    _parseSchema: (schemaDef) ->
      _.each schemaDef, (val, key, list) =>
        if key isnt exports.constants.CHILDREN
          @_properties[key] = val
        else
          @_parseLanguages(val)
          @_parseFields(val)

    # return top level formjson properties
    get: (property) ->
      return @_properties[property]

    onload: (data) ->
      @_parseSchema data

    getFields: ()->
      return @_fields

    getFieldByName: (name) ->
      return _.find @_fields, (field) ->
        return field.name() is name

    getFieldsByType: (typeName) ->
      return _.filter @_fields, (field) ->
        return field.type() is typeName

    getSupportedLanguages: ->
      return @_supportedLanguages

  class exports.DataManager extends exports.Manager
    @typeMap = {}
    @typeMap[exports.constants.INTEGER] = dv.type.numeric;
    @typeMap[exports.constants.DECIMAL] = dv.type.numeric;
    @typeMap[exports.constants.SELECT_ONE] = dv.type.nominal;
    @typeMap[exports.constants.TEXT] = dv.type.unknown;
    @typeMap[exports.constants.SELECT_MULTIPLE] = dv.type.unknown;
    @typeMap[exports.constants.ID] = dv.type.unknown;

    constructor: (@_schemaManager) ->
      @_dvTable = null

    _pushToStore: (responses) ->
      dvData = {}
      @_dvTable = dv.table()

      # chuck all questions whose type isn't in typeMap; add an _id "question"
      # TODO: if datavore is our only datastore, this chucking can be removed (with care)
      fields = _.filter @_schemaManager.getFields(), (field) =>
        if DataManager.typeMap.hasOwnProperty field.type()
          dvData[field.name()] = []
          return true
        return false

      # for each response
      _.each responses, (response) =>
        # for each field
        _.each fields, (field) =>
          dvData[field.name()].push response[field.name()]

      _.each fields, (field) =>
        @_dvTable.addColumn(field.name(), dvData[field.name()], DataManager.typeMap[field.type()]);


    onload: (data) ->
      # push data to datavore store
      @_pushToStore(data)

    dvQuery: (query) ->
      return this._dvTable.query(query)

    groupBy: (fieldName) ->
      try
        result = @_dvTable.query({vals: [dv.count()], dims: [fieldName]})
        # format as object
        return _.object(result[0], result[1])
      catch e
        throw new Error("field \"#{fieldName}\" does not exist")



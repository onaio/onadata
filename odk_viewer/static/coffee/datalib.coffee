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
    GEOLOCATION: "_geolocation", DATASET_OPTIONS: "dataset_options", GRID_EL: "grid_el", MAP_EL: "map_el"
  };

  class exports.Datalib extends Backbone.Model
    constructor: (options) ->
      super options
      dataset_options = @get(exports.constants.DATASET_OPTIONS)
      @dataset = new recline.Model.Dataset(dataset_options)

    _setupGrid: () =>
      el = $(@get(exports.constants.GRID_EL))
      @_gridview = new recline.View.Grid({
        model: @dataset,
        el: el
      });
      @_gridview.visible = true;
      @_gridview.render()

    _setupMap: () =>
      el = $(@get(exports.constants.MAP_EL))
      @_mapview = new recline.View.Map({
        model: @dataset
      })
      el.append(@_mapview.el)
      @_mapview.render()

    _setupViews: () =>
      @_setupGrid()
      @_setupMap()

    init: ()->
      deferred = @dataset.fetch()
      deferred.done(@_setupViews)
      return deferred

  class exports.Map extends Backbone.View
    constructor: () ->

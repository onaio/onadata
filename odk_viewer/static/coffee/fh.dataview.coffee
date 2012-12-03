namespace = (target, name, block) ->
  [target, name, block] = [(if typeof exports isnt 'undefined' then exports else window), arguments...] if arguments.length < 3
  top    = target
  target = target[item] or= {} for item in name.split '.'
  block target, top

namespace 'fh', (exports) ->
  class exports.DataView extends Backbone.View

    constructor: (options) ->
      super options
      @template = options.template
      @views = options.views
      @render()

    render: () ->
      tmplData = {}
      tmplData.views = @views
      template = Mustache.render(@template, tmplData);
      @$el.html(template)

      # render the views
      $dataViewContainer = this.$el.find('.data-view-container');

      _.each @views, (view, pageName) ->
        view.view.render()
        $dataViewContainer.append(view.view.el);

      return @


  class exports.Map extends Backbone.View
    @defaults: {
      zoom: 8,
      className: 'fh-map-container',
      template: fh.template.map
    }

    constructor: (options) ->
      options = _.extend(exports.Map.defaults, options)
      super options
      @template = @options.template
      @featureLayers = @options.featureLayers

    render: () ->
      tmplData = {}
      template = Mustache.render(@template, tmplData);
      @$el.html(template)

      # setup map within render so that we have a valid map container element that was just created above
      @_setupMap()

      # render child layers
      _.each @featureLayers, (layer) =>
        layer.render()

    _setupMap: () ->
      @$map_el = @$el.find('.map')
      @map = new L.Map(@$map_el.get(0))

      #todo: load mapbox urls through wax to got tilejson(s) - also allow for additional maps - we'll just merge the two lists before we load
      mapUrl = "http://otile{s}.mqcdn.com/tiles/1.0.0/osm/{z}/{x}/{y}.png";
      osmAttribution = 'Map data &copy; 2011 OpenStreetMap contributors, Tiles Courtesy of <a href="http://www.mapquest.com/" target="_blank">MapQuest</a> <img src="http://developer.mapquest.com/content/osm/mq_logo.png">';
      layer = new L.TileLayer(mapUrl, {maxZoom: 18, attribution: osmAttribution ,subdomains: '1234'});
      @map.addLayer(layer)
      @map.setView(@options.center, @options.zoom)

  class exports.FeatureLayer extends Backbone.View
    constructor: (options) ->
      super options
      # setup our state
      state = _.extend({
        geoField: null
      }, options.state)
      @state = new recline.Model.ObjectState(state)
      # bind field.reset so we know when fields are avilable to consume -  we'll bind reDraw to geoField change as well when its updated via the  UI
      @model.fields.bind('reset', @_setGeoField, @)
      # bind to records.add so we re-draw the markers
      @model.records.bind('reset', @_reDraw, @)

    _reDraw: () ->
      # make sure we have set a geo field
      @_setGeoField()
      # get the geofield from the state
      geoField = @state.get(fh.constants.GEOFIELD)
      # generate the geojson - todo: we should be able to add features/points to the existing geojson for performance - look at the recline map on how
      geoJson = @model.records.each (record) =>
        console.log(record)

    _setGeoField: () ->
      # check if we have a geopoint in our state, if not, pick the first one from the list
      if not @state.get(fh.constants.GEOFIELD)
        gpsfields = @model.fieldsByFhType(fh.constants.GEOPOINT)
        @state.set(fh.constants.GEOFIELD, gpsfields.at(0).get('id'))

    # implement render in subclasses - mainly to setup legend and hexbin indicator elements - need the map object for that me thinks -
    # or not if the map directly accesses the el and renders it, positioning to be setup by css
    # render: () ->

  class exports.MarkerLayer extends exports.FeatureLayer
    constructor: (options) ->
      super options
      @model.fields

    render: () ->
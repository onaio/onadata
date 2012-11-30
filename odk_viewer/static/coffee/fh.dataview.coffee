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

    class MapOptions extends Backbone.Model
      defaults: {
        zoom: 8,
        className: 'fh-map-container',
        template: fh.template.map
      }

    constructor: (options) ->
      mapOptions = new MapOptions(options)
      super mapOptions.attributes
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

    _reDraw: () ->
      console.log(arguments)
      console.log("Re-drawing...")

  class exports.MarkerLayer extends exports.FeatureLayer
    constructor: (options) ->
      super options
      @model.fields

    render: () ->
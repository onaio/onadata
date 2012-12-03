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

    _setupMap: () ->
      @$map_el = @$el.find('.map')
      @map = new L.Map(@$map_el.get(0))

      #todo: load mapbox urls through wax to get tilejson(s) - also allow for additional maps - we'll just merge the two lists before we load
      mapUrl = "http://otile{s}.mqcdn.com/tiles/1.0.0/osm/{z}/{x}/{y}.png";
      osmAttribution = 'Map data &copy; 2011 OpenStreetMap contributors, Tiles Courtesy of <a href="http://www.mapquest.com/" target="_blank">MapQuest</a> <img src="http://developer.mapquest.com/content/osm/mq_logo.png">';
      layer = new L.TileLayer(mapUrl, {maxZoom: 18, attribution: osmAttribution ,subdomains: '1234'});
      @map.addLayer(layer)

    render: () ->
      tmplData = {}
      template = Mustache.render(@template, tmplData);
      @$el.html(template)

      # setup map within render so that we have a valid map container element that was just created above
      @_setupMap()

      # render child layers by adding their respective L.Layer - todo: when/where do we append legends etc.
      _.each @featureLayers, (featureLayer) =>
        # add the leaflet layer
        @map.addLayer(featureLayer.layer)

        # render to let feature layer setup its html elements for legends etc
        featureLayer.render(@map)

        # attach feature layer re-draw event
        featureLayer.bind('redraw', @_fitBounds, @)

    _fitBounds: () ->
      # todo: map should decide if it should re-fit e.g. user zooms in and does a "view by" selection - we don't want to re-fit
      # fit bounds from all the layers
      bounds = new L.LatLngBounds()
      _.each @featureLayers, (featureLayer) =>
        bounds.extend(featureLayer.bounds)
      @map.fitBounds(bounds)

  class exports.FeatureLayer extends Backbone.View
    @defaults: {
      label: "Feature Layer"
    }

    constructor: (options) ->
      options = _.extend(exports.Map.defaults, options)
      super options

      # setup our state
      state = _.extend({
        geoField: null
      }, options.state)

      @label = options.label
      @state = new recline.Model.ObjectState(state)
      # bind field.reset so we know when fields are avilable to consume -  we'll bind reDraw to geoField change as well when its updated via the  UI
      @model.fields.bind('reset', @_setGeoField, @)
      # bind to records.add so we re-draw the markers
      @model.records.bind('reset', @_reDraw, @)
      # lat/lng bounds for this feature layer so the parent map knows how to set bounds on re-draws
      @bounds = new L.LatLngBounds()

    # implement render in subclasses - mainly to setup legend and hexbin indicator elements - need the map object for that me thinks -
    # or not if the map directly accesses the el and renders it, positioning to be setup by css
    # render: () ->

    _reDraw: () ->
      # make sure we have set a geo field
      @_setGeoField()

    _setGeoField: () ->
      # check if we have a geopoint in our state, if not, pick the first one from the list
      if not @state.get(fh.constants.GEOFIELD)
        gpsfields = @model.fieldsByFhType(fh.constants.GEOPOINT)
        @state.set(fh.constants.GEOFIELD, gpsfields.at(0).get('id'))

  class exports.MarkerLayer extends exports.FeatureLayer
    constructor: (options) ->
      super options
      @model.fields
      @layer = new L.LayerGroup()

    render: () ->

    _reDraw: () ->
      # call super to set our geo-field
      super

      # clear layers
      @layer.clearLayers()

      # get the geofield from the state
      geoField = @state.get(fh.constants.GEOFIELD)

      # generate the geojson - todo: we should be able to add features/points to the existing geojson for performance - look at the recline map on how
      features = @model.records.reduce ( (featuresMemo, record, records) =>
        # get the geo data
        geopoint = record.get(geoField)
        if geopoint
          # TODO: temporary, we should have a pre-parsed geo structure whe we get here
          geoparts = geopoint.split(" ")
          lat = geoparts[0]
          lng =geoparts[1]
          @bounds.extend(new L.LatLng(lat, lng))
          # todo: every record needs to have an id since this can come forms source thats not formhub, perhaps an option setting idField
          id = record.get('_id')
          geometry = {"type":"Point", "coordinates": [lng, lat]};
          feature = {"type": "Feature", "id": id, "geometry":geometry, "properties": record.attributes};
          featuresMemo.push(feature)
        return featuresMemo
      ), []
      geoJSON = {"type":"FeatureCollection", "features": features}

      # todo- restyle layer ideally through config so its easy to change te markers from the outside
      geojsonLayer = L.geoJson(geoJSON)
      @layer.addLayer(geojsonLayer)

      # trigger a redraw event - primarily for the map to re-fit bounds
      @trigger('redraw', @)

namespace = (target, name, block) ->
  [target, name, block] = [(if typeof exports isnt 'undefined' then exports else window), arguments...] if arguments.length < 3
  top    = target
  target = target[item] or= {} for item in name.split '.'
  block target, top

namespace 'fh.map', (exports) ->
  _map = undefined
  _layersControl = undefined

  exports.getMap = ->
    return _map

  exports.init = (mapId) ->
    _map = new L.Map(mapId)
    _layersControl = new L.Control.Layers();
    _map.addControl(_layersControl);
    return null

  exports.addBaseLayer = (baseLayer, label, isDefault) ->
    _layersControl.addBaseLayer(baseLayer, label)
    if isDefault
      _map.addLayer(baseLayer)

  exports.addlayer = (layer) ->

  exports.addTileJSON = (url, label, isDefault, extraAttribution) ->
    _tilejsonLoaded = (tilejson) =>
      tilejson.attribution += if extraAttribution? then " - " + extraAttribution else null
      tileLayer = new wax.leaf.connector(tilejson);
      exports.addBaseLayer(tileLayer, label, isDefault);
    wax.tilejson(url, _tilejsonLoaded);
namespace = (target, name, block) ->
  [target, name, block] = [(if typeof exports isnt 'undefined' then exports else window), arguments...] if arguments.length < 3
  top    = target
  target = target[item] or= {} for item in name.split '.'
  block target, top

namespace 'fh.map', (exports) ->
  _map = undefined
  _layersControl = undefined

  _tileJSONLoaded = (tilejson) =>
    tileLayer = new wax.leaf.connector(tilejson);
    layersControl.addBaseLayer(tileLayer, mapData.label);


  exports.init = (mapId) ->
    _map = new L.Map(mapId)
    _layersControl = new L.Control.Layers();
    _map.addControl(_layersControl);
    return null

  exports.addBaselayer = (baseLayer) ->
    _layersControl.addBaseLayer(baseLayer)

  exports.addlayer = (layer) ->

  exports.addTileJSON = () ->
    wax.tilejson(mapData.url, _tileJSONLoaded);
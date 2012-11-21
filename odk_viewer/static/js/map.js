(function() {
  var namespace,
    __slice = [].slice;

  namespace = function(target, name, block) {
    var item, top, _i, _len, _ref, _ref1;
    if (arguments.length < 3) {
      _ref = [(typeof exports !== 'undefined' ? exports : window)].concat(__slice.call(arguments)), target = _ref[0], name = _ref[1], block = _ref[2];
    }
    top = target;
    _ref1 = name.split('.');
    for (_i = 0, _len = _ref1.length; _i < _len; _i++) {
      item = _ref1[_i];
      target = target[item] || (target[item] = {});
    }
    return block(target, top);
  };

  namespace('fh.map', function(exports) {
    var _layersControl, _map, _tileJSONLoaded,
      _this = this;
    _map = void 0;
    _layersControl = void 0;
    _tileJSONLoaded = function(tilejson) {
      var tileLayer;
      tileLayer = new wax.leaf.connector(tilejson);
      return layersControl.addBaseLayer(tileLayer, mapData.label);
    };
    exports.init = function(mapId) {
      _map = new L.Map(mapId);
      _layersControl = new L.Control.Layers();
      _map.addControl(_layersControl);
      return null;
    };
    exports.addBaselayer = function(baseLayer) {
      return _layersControl.addBaseLayer(baseLayer);
    };
    exports.addlayer = function(layer) {};
    return exports.addTileJSON = function() {
      return wax.tilejson(mapData.url, _tileJSONLoaded);
    };
  });

}).call(this);

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
    var _layersControl, _map;
    _map = void 0;
    _layersControl = void 0;
    exports.getMap = function() {
      return _map;
    };
    exports.init = function(mapId) {
      _map = new L.Map(mapId);
      _layersControl = new L.Control.Layers();
      _map.addControl(_layersControl);
      return null;
    };
    exports.addBaseLayer = function(baseLayer, label, isDefault) {
      _layersControl.addBaseLayer(baseLayer, label);
      if (isDefault) {
        return _map.addLayer(baseLayer);
      }
    };
    exports.addlayer = function(layer) {};
    return exports.addTileJSON = function(url, label, isDefault, extraAttribution) {
      var _tilejsonLoaded,
        _this = this;
      _tilejsonLoaded = function(tilejson) {
        var tileLayer;
        tilejson.attribution += extraAttribution != null ? " - " + extraAttribution : null;
        tileLayer = new wax.leaf.connector(tilejson);
        return exports.addBaseLayer(tileLayer, label, isDefault);
      };
      return wax.tilejson(url, _tilejsonLoaded);
    };
  });

}).call(this);

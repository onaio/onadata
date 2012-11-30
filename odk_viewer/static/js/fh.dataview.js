(function() {
  var namespace,
    __slice = [].slice,
    __hasProp = {}.hasOwnProperty,
    __extends = function(child, parent) { for (var key in parent) { if (__hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; };

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

  namespace('fh', function(exports) {
    exports.DataView = (function(_super) {

      __extends(DataView, _super);

      function DataView(options) {
        DataView.__super__.constructor.call(this, options);
        this.template = options.template;
        this.views = options.views;
        this.render();
      }

      DataView.prototype.render = function() {
        var $dataViewContainer, template, tmplData;
        tmplData = {};
        tmplData.views = this.views;
        template = Mustache.render(this.template, tmplData);
        this.$el.html(template);
        $dataViewContainer = this.$el.find('.data-view-container');
        _.each(this.views, function(view, pageName) {
          view.view.render();
          return $dataViewContainer.append(view.view.el);
        });
        return this;
      };

      return DataView;

    })(Backbone.View);
    exports.Map = (function(_super) {
      var MapOptions;

      __extends(Map, _super);

      MapOptions = (function(_super1) {

        __extends(MapOptions, _super1);

        function MapOptions() {
          return MapOptions.__super__.constructor.apply(this, arguments);
        }

        MapOptions.prototype.defaults = {
          zoom: 8,
          className: 'fh-map-container',
          template: fh.template.map
        };

        return MapOptions;

      })(Backbone.Model);

      function Map(options) {
        var mapOptions;
        mapOptions = new MapOptions(options);
        Map.__super__.constructor.call(this, mapOptions.attributes);
        this.template = this.options.template;
        this.featureLayers = this.options.featureLayers;
      }

      Map.prototype.render = function() {
        var template, tmplData,
          _this = this;
        tmplData = {};
        template = Mustache.render(this.template, tmplData);
        this.$el.html(template);
        this._setupMap();
        return _.each(this.featureLayers, function(layer) {
          return layer.render();
        });
      };

      Map.prototype._setupMap = function() {
        var layer, mapUrl, osmAttribution;
        this.$map_el = this.$el.find('.map');
        this.map = new L.Map(this.$map_el.get(0));
        mapUrl = "http://otile{s}.mqcdn.com/tiles/1.0.0/osm/{z}/{x}/{y}.png";
        osmAttribution = 'Map data &copy; 2011 OpenStreetMap contributors, Tiles Courtesy of <a href="http://www.mapquest.com/" target="_blank">MapQuest</a> <img src="http://developer.mapquest.com/content/osm/mq_logo.png">';
        layer = new L.TileLayer(mapUrl, {
          maxZoom: 18,
          attribution: osmAttribution,
          subdomains: '1234'
        });
        this.map.addLayer(layer);
        return this.map.setView(this.options.center, this.options.zoom);
      };

      return Map;

    })(Backbone.View);
    exports.FeatureLayer = (function(_super) {

      __extends(FeatureLayer, _super);

      function FeatureLayer(options) {
        var state;
        FeatureLayer.__super__.constructor.call(this, options);
        state = _.extend({
          geoField: null
        }, options.state);
        this.state = new recline.Model.ObjectState(state);
        this.model.fields.bind('reset', this._setGeoField, this);
        this.model.records.bind('reset', this._reDraw, this);
      }

      FeatureLayer.prototype._reDraw = function() {
        var geoField;
        this._setGeoField();
        return geoField = this.state.get(fh.constants.GEOFIELD);
      };

      FeatureLayer.prototype._setGeoField = function() {
        var gpsfields;
        if (!this.state.get(fh.constants.GEOFIELD)) {
          gpsfields = this.model.fieldsByFhType(fh.constants.GEOPOINT);
          return this.state.set(fh.constants.GEOFIELD, gpsfields.at(0).get('id'));
        }
      };

      return FeatureLayer;

    })(Backbone.View);
    return exports.MarkerLayer = (function(_super) {

      __extends(MarkerLayer, _super);

      function MarkerLayer(options) {
        MarkerLayer.__super__.constructor.call(this, options);
        this.model.fields;
      }

      MarkerLayer.prototype.render = function() {};

      return MarkerLayer;

    })(exports.FeatureLayer);
  });

}).call(this);

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

      __extends(Map, _super);

      Map.defaults = {
        zoom: 8,
        className: 'fh-map-container',
        template: fh.template.map
      };

      function Map(options) {
        options = _.extend(exports.Map.defaults, options);
        Map.__super__.constructor.call(this, options);
        this.template = this.options.template;
        this.featureLayers = this.options.featureLayers;
      }

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
        return this.map.addLayer(layer);
      };

      Map.prototype.render = function() {
        var template, tmplData,
          _this = this;
        tmplData = {};
        template = Mustache.render(this.template, tmplData);
        this.$el.html(template);
        this._setupMap();
        return _.each(this.featureLayers, function(featureLayer) {
          _this.map.addLayer(featureLayer.layer);
          featureLayer.render(_this.map);
          return featureLayer.bind('redraw', _this._fitBounds, _this);
        });
      };

      Map.prototype._fitBounds = function() {
        var bounds,
          _this = this;
        bounds = new L.LatLngBounds();
        _.each(this.featureLayers, function(featureLayer) {
          return bounds.extend(featureLayer.bounds);
        });
        return this.map.fitBounds(bounds);
      };

      return Map;

    })(Backbone.View);
    exports.FeatureLayer = (function(_super) {

      __extends(FeatureLayer, _super);

      FeatureLayer.defaults = {
        label: "Feature Layer"
      };

      function FeatureLayer(options) {
        var state;
        options = _.extend(exports.Map.defaults, options);
        FeatureLayer.__super__.constructor.call(this, options);
        state = _.extend({
          geoField: null
        }, options.state);
        this.label = options.label;
        this.state = new recline.Model.ObjectState(state);
        this.model.fields.bind('reset', this._setGeoField, this);
        this.model.records.bind('reset', this._reDraw, this);
        this.bounds = new L.LatLngBounds();
      }

      FeatureLayer.prototype._reDraw = function() {
        return this._setGeoField();
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
        this.layer = new L.LayerGroup();
      }

      MarkerLayer.prototype.render = function() {};

      MarkerLayer.prototype._reDraw = function() {
        var features, geoField, geoJSON, geojsonLayer,
          _this = this;
        MarkerLayer.__super__._reDraw.apply(this, arguments);
        this.layer.clearLayers();
        geoField = this.state.get(fh.constants.GEOFIELD);
        features = this.model.records.reduce((function(featuresMemo, record, records) {
          var feature, geometry, geoparts, geopoint, id, lat, lng;
          geopoint = record.get(geoField);
          if (geopoint) {
            geoparts = geopoint.split(" ");
            lat = geoparts[0];
            lng = geoparts[1];
            _this.bounds.extend(new L.LatLng(lat, lng));
            id = record.get('_id');
            geometry = {
              "type": "Point",
              "coordinates": [lng, lat]
            };
            feature = {
              "type": "Feature",
              "id": id,
              "geometry": geometry,
              "properties": record.attributes
            };
            featuresMemo.push(feature);
          }
          return featuresMemo;
        }), []);
        geoJSON = {
          "type": "FeatureCollection",
          "features": features
        };
        geojsonLayer = L.geoJson(geoJSON);
        this.layer.addLayer(geojsonLayer);
        return this.trigger('redraw', this);
      };

      return MarkerLayer;

    })(exports.FeatureLayer);
  });

}).call(this);

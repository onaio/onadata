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
    exports.constants = {
      NAME: "name",
      LABEL: "label",
      TYPE: "type",
      CHILDREN: "children",
      TEXT: "text",
      INTEGER: "integer",
      DECIMAL: "decimal",
      SELECT_ONE: "select one",
      SELECT_MULTIPLE: "select multiple",
      GROUP: "group",
      HINT: "hint",
      GEOPOINT: "geopoint",
      ID: "_id",
      START: "start",
      LIMIT: "limit",
      COUNT: "count",
      FIELDS: "fields",
      GEOLOCATION: "_geolocation"
    };
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
    return exports.Map = (function(_super) {
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
      }

      Map.prototype.render = function() {
        var template, tmplData;
        tmplData = {};
        template = Mustache.render(this.template, tmplData);
        this.$el.html(template);
        return this._setupMap();
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
  });

}).call(this);

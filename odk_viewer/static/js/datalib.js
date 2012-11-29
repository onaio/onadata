(function() {
  var namespace,
    __slice = [].slice,
    __bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; },
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
      GEOLOCATION: "_geolocation",
      DATASET_OPTIONS: "dataset_options",
      GRID_EL: "grid_el",
      MAP_EL: "map_el"
    };
    exports.Datalib = (function(_super) {

      __extends(Datalib, _super);

      function Datalib(options) {
        this._setupViews = __bind(this._setupViews, this);

        this._setupMap = __bind(this._setupMap, this);

        this._setupGrid = __bind(this._setupGrid, this);

        var dataset_options;
        Datalib.__super__.constructor.call(this, options);
        dataset_options = this.get(exports.constants.DATASET_OPTIONS);
        this.dataset = new recline.Model.Dataset(dataset_options);
      }

      Datalib.prototype._setupGrid = function() {
        var el;
        el = $(this.get(exports.constants.GRID_EL));
        this._gridview = new recline.View.Grid({
          model: this.dataset,
          el: el
        });
        this._gridview.visible = true;
        return this._gridview.render();
      };

      Datalib.prototype._setupMap = function() {
        var el;
        el = $(this.get(exports.constants.MAP_EL));
        this._mapview = new recline.View.Map({
          model: this.dataset
        });
        el.append(this._mapview.el);
        return this._mapview.render();
      };

      Datalib.prototype._setupViews = function() {
        this._setupGrid();
        return this._setupMap();
      };

      Datalib.prototype.init = function() {
        var deferred;
        deferred = this.dataset.fetch();
        deferred.done(this._setupViews);
        return deferred;
      };

      return Datalib;

    })(Backbone.Model);
    return exports.Map = (function(_super) {

      __extends(Map, _super);

      function Map() {}

      return Map;

    })(Backbone.View);
  });

}).call(this);

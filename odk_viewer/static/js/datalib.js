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
    exports.Reader = (function() {

      function Reader() {}

      Reader.prototype.read = function(data) {
        return data;
      };

      return Reader;

    })();
    exports.Loader = (function() {

      function Loader(_reader) {
        this._reader = _reader;
        if (typeof this._reader === "undefined" || this._reader === null) {
          throw new Error("You must provide a valid reader");
        }
      }

      return Loader;

    })();
    exports.MemoryLoader = (function(_super) {

      __extends(MemoryLoader, _super);

      function MemoryLoader(_reader, _data) {
        this._data = _data;
        MemoryLoader.__super__.constructor.call(this, _reader);
      }

      MemoryLoader.prototype.load = function() {
        var deferred, parsed_data;
        deferred = $.Deferred();
        if (typeof this._data !== "undefined" && this._data !== null) {
          parsed_data = this._reader.read(this._data);
          deferred.resolve(parsed_data);
        } else {
          deferred.reject({
            "error": "No data available."
          });
        }
        return deferred.promise();
      };

      return MemoryLoader;

    })(exports.Loader);
    exports.AjaxLoader = (function(_super) {

      __extends(AjaxLoader, _super);

      function AjaxLoader(_reader, _url, _params) {
        this._url = _url;
        this._params = _params;
        AjaxLoader.__super__.constructor.call(this, _reader);
      }

      AjaxLoader.prototype.load = function() {
        var deferred, promise,
          _this = this;
        deferred = $.Deferred();
        promise = $.get(this._url, this._params);
        promise.done(function(data) {
          var parsed_data;
          parsed_data = _this._reader.read(data);
          return deferred.resolve(parsed_data);
        });
        promise.fail(function(e) {
          return deferred.reject(e);
        });
        return deferred.promise();
      };

      return AjaxLoader;

    })(exports.Loader);
    exports.Field = (function() {

      function Field(fieldDef) {
        var _this = this;
        this._name = fieldDef.name;
        this._setType(fieldDef.type);
        this._hint = fieldDef.hasOwnProperty(exports.constants.HINT) ? fieldDef.hint : null;
        this._label = fieldDef.hasOwnProperty(exports.constants.LABEL) ? fieldDef.label : null;
        this._options = [];
        if (fieldDef.hasOwnProperty(exports.constants.CHILDREN)) {
          _.each(fieldDef.children, function(val, key, list) {
            return _this._options.push(new exports.Field(val));
          });
        }
      }

      Field.prototype._setType = function(typeName) {
        return this._type = typeName;
      };

      Field.prototype.name = function() {
        return this._name;
      };

      Field.prototype.type = function() {
        return this._type;
      };

      Field.prototype.hint = function() {
        return this._hint;
      };

      Field.prototype.label = function(language) {
        if (typeof language !== "undefined" && language !== null) {
          return this._label[language];
        } else {
          if (typeof this._label === "object") {
            return _.values(this._label)[0];
          } else {
            return this._label;
          }
        }
      };

      Field.prototype.options = function() {
        return this._options;
      };

      return Field;

    })();
    exports.Manager = (function() {

      function Manager() {}

      Manager.prototype.init = function(_loader) {
        var promise,
          _this = this;
        this._loader = _loader;
        promise = this._loader.load();
        promise.done(function(data) {
          return _this.onload(data);
        });
        promise.fail(function(e) {
          return _this.onfail(e);
        });
        return promise;
      };

      Manager.prototype.onload = function(data) {};

      Manager.prototype.onfail = function(e) {};

      return Manager;

    })();
    exports.SchemaManager = (function(_super) {

      __extends(SchemaManager, _super);

      function SchemaManager() {
        this._fields = [];
        this._properties = {};
        this._supportedLanguages = [];
      }

      SchemaManager.prototype._parseLanguages = function(fieldsDef) {
        var field, label;
        field = _.find(fieldsDef, function(field) {
          return field.hasOwnProperty(exports.constants.LABEL);
        });
        label = field.label;
        return this._supportedLanguages = typeof label === "object" ? _.keys(label) : ["default"];
      };

      SchemaManager.prototype._parseFields = function(fieldsDef) {
        var _this = this;
        return _.each(fieldsDef, function(fieldObject, index, list) {
          if (fieldObject.type !== exports.constants.GROUP) {
            return _this._fields.push(new exports.Field(fieldObject));
          } else if (fieldObject.type === exports.constants.GROUP && fieldObject.hasOwnProperty(exports.constants.CHILDREN)) {
            return _this._parseFields(fieldObject.children);
          }
        });
      };

      SchemaManager.prototype._parseSchema = function(schemaDef) {
        var _this = this;
        return _.each(schemaDef, function(val, key, list) {
          if (key !== exports.constants.CHILDREN) {
            return _this._properties[key] = val;
          } else {
            _this._parseLanguages(val);
            return _this._parseFields(val);
          }
        });
      };

      SchemaManager.prototype.get = function(property) {
        return this._properties[property];
      };

      SchemaManager.prototype.onload = function(data) {
        return this._parseSchema(data);
      };

      SchemaManager.prototype.getFields = function() {
        return this._fields;
      };

      SchemaManager.prototype.getFieldByName = function(name) {
        return _.find(this._fields, function(field) {
          return field.name() === name;
        });
      };

      SchemaManager.prototype.getFieldsByType = function(typeName) {
        return _.filter(this._fields, function(field) {
          return field.type() === typeName;
        });
      };

      SchemaManager.prototype.getSupportedLanguages = function() {
        return this._supportedLanguages;
      };

      return SchemaManager;

    })(exports.Manager);
    return exports.DataManager = (function(_super) {

      __extends(DataManager, _super);

      DataManager.typeMap = {};

      DataManager.typeMap[exports.constants.INTEGER] = dv.type.numeric;

      DataManager.typeMap[exports.constants.DECIMAL] = dv.type.numeric;

      DataManager.typeMap[exports.constants.SELECT_ONE] = dv.type.nominal;

      DataManager.typeMap[exports.constants.TEXT] = dv.type.unknown;

      DataManager.typeMap[exports.constants.SELECT_MULTIPLE] = dv.type.unknown;

      DataManager.typeMap[exports.constants.ID] = dv.type.unknown;

      function DataManager(_schemaManager) {
        this._schemaManager = _schemaManager;
        this._dvTable = null;
      }

      DataManager.prototype._pushToStore = function(responses) {
        var dvData, fields,
          _this = this;
        dvData = {};
        this._dvTable = dv.table();
        fields = _.filter(this._schemaManager.getFields(), function(field) {
          if (DataManager.typeMap.hasOwnProperty(field.type())) {
            dvData[field.name()] = [];
            return true;
          }
          return false;
        });
        _.each(responses, function(response) {
          return _.each(fields, function(field) {
            return dvData[field.name()].push(response[field.name()]);
          });
        });
        return _.each(fields, function(field) {
          return _this._dvTable.addColumn(field.name(), dvData[field.name()], DataManager.typeMap[field.type()]);
        });
      };

      DataManager.prototype.onload = function(data) {
        return this._pushToStore(data);
      };

      DataManager.prototype.dvQuery = function(query) {
        return this._dvTable.query(query);
      };

      DataManager.prototype.groupBy = function(fieldName) {
        var result;
        try {
          result = this._dvTable.query({
            vals: [dv.count()],
            dims: [fieldName]
          });
          return _.object(result[0], result[1]);
        } catch (e) {
          throw new Error("field \"" + fieldName + "\" does not exist");
        }
      };

      return DataManager;

    })(exports.Manager);
  });

}).call(this);

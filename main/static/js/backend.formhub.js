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

namespace('recline.Backend.Formhub', function(exports) {
  var _fhToReclineType, _parseSchema;
  exports.__type__ = 'formhub';
  _fhToReclineType = function(fhTypeName) {
    var fhTypes;
    fhTypes = {};
    fhTypes[fh.constants.GEOPOINT] = "geo_point";
    return fhTypes[fhTypeName] || "string";
  };
  _parseSchema = function(schema) {
    var fields, metadata, parseFields,
      _this = this;
    metadata = {};
    fields = [];
    parseFields = function(fieldsDef) {
      return _.each(fieldsDef, function(fieldObject, index, list) {
        var field, _ref, _ref1;
        if (fieldObject.type !== fh.constants.GROUP) {
          field = {
            id: fieldObject.name
          };
          if (fieldObject.label && typeof metadata.languages === "undefined") {
            if (typeof fieldObject.label === "object") {
              metadata.languages = _.keys(fieldObject.label);
            } else {
              metadata.languages = ["default"];
            }
          }
          field.type = _fhToReclineType((_ref = fieldObject[fh.constants.TYPE]) != null ? _ref : null);
          field[fh.constants.FH_TYPE] = (_ref1 = fieldObject[fh.constants.TYPE]) != null ? _ref1 : null;
          field.label = typeof fieldObject.label === "function" ? fieldObject.label(null) : void 0;
          return fields.push(field);
        } else if (fieldObject.type === exports.constants.GROUP && fieldObject.hasOwnProperty(exports.constants.CHILDREN)) {
          return parseFields(fieldObject.children);
        }
      });
    };
    _.each(schema, function(val, key) {
      if (key !== fh.constants.CHILDREN) {
        return metadata[key] = val;
      }
    });
    parseFields(schema.children);
    return {
      metadata: metadata,
      fields: fields
    };
  };
  exports.fetch = function(dataset) {
    var deferred, jqXHR;
    deferred = $.Deferred();
    jqXHR = $.getJSON(dataset.formurl);
    jqXHR.done(function(schema) {
      schema = _parseSchema(schema);
      return deferred.resolve({
        metadata: schema.metadata,
        fields: schema.fields
      });
    });
    jqXHR.fail(function(e) {
      return deferred.reject(e);
    });
    return deferred.promise();
  };
  return exports.query = function(queryObj, dataset) {
    var deferred, jqXHR, params;
    deferred = $.Deferred();
    params = {
      count: 1
    };
    jqXHR = $.getJSON(dataset.dataurl, params);
    jqXHR.done(function(data) {
      var total;
      total = data[0].count;
      params = {
        start: queryObj.from,
        limit: queryObj.size
      };
      jqXHR = $.getJSON(dataset.dataurl, params);
      return jqXHR.done(function(data) {
        return deferred.resolve({
          total: total,
          hits: data
        });
      });
    });
    jqXHR.fail(function(e) {
      return deferred.reject(e);
    });
    return deferred.promise();
  };
});

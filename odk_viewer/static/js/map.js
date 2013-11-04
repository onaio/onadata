// FH.Map Closure
// ------------------
(function(){
    "use strict";
    // Save a reference to the global object (`window` in the browser, `exports`
    // on the server).
    var root = this,
        // Default map options.
        defaults = {
            layers: [],
            zoom: 8,
            center: [0, 0]
        },
        LayerFactories = {};

    // Check if the `FH` namespace already exists and create it otherwise. We'll
    // attach all our exposed objects to it.
    var FH = root.FH = root.FH || {};

    // Map type constants
    FH.layers = {
        MAPBOX: 'MapBox',
        CLOUD_MADE: 'CloudMade',
        OPEN_STREET_MAP: 'OSM',
        OPEN_CYCLE_MAP: 'OCM',
        GOOGLE: 'Google',
        GENERIC: 'Genric'
    };

    // ### FH.Map Object
    // Create an instance of this for every map you want to have on the page.
    // ```javascript
    // var map = new FH.Map({
    //     el: $('#map_el_id'),
    //     zoom: 8
    //     center: [36.1, -1.03],
    //     base_layers: [
    //        {
    //            type: FH.Map.MAPBOX,
    //            label: "My Map",
    //            options: {
    //                user: "modilabs",
    //                map: "map-iuetkf9u",
    //                attribution: "Map data (c) OpenStreetMap contributors, CC-BY-SA"
    //            }
    //         }
    //     ]
    // });
    // ```
    FH.Map = Backbone.View.extend({
        // #### Initialize the map
        // Called when a new map is constructed, we initialize the leaflet map
        // here.
        initialize: function () {
            var default_layer_config,
                _that = this;

            // Populate un-specified options with defaults
            _.defaults(this.options, defaults);

            // Create the layers control
            this._layers_control = new L.Control.Layers();

            // Initialize the leaflet `_map` and assign it as a property of this
            // FH.Map instance
            this._map = L.map(this.el, {
                zoom: this.options.zoom,
                center: this.options.center
            }).addControl(this._layers_control);

            // Create the FeatureLayerSet
            this.feature_layers = new FH.FeatureLayerSet();

            // determine the default layer
            default_layer_config = FH.Map.determineDefaultLayer(this.options.layers);

            // Add base layers that were defined within options
            this.options.layers.forEach(function (layer_config) {
                // is this layer the we determined to be our default
                var is_default = default_layer_config === layer_config;
                _that.addBaseLayer(layer_config, is_default);
            });
        },

        // #### Add a base layer
        // The map must already be initialised
        addBaseLayer: function (layer_config, is_default) {
            // If type is not defined, set it to generic.
            layer_config.type = layer_config.type || FH.layers.GENERIC;

            // Call the appropriate function to instantiate a layer of this type.
            var layer = new LayerFactories[layer_config.type](layer_config.options);

            // Add the layer to the layer's control.
            this._layers_control.addBaseLayer(layer, layer_config.label);

            // If the is_default flag is set, add it to the map.
            if(is_default) {
                this._map.addLayer(layer);
            }
            return layer;
        },

        addFeatureLayer: function (form_url, data_url) {
            var feature_layer = new FeatureLayer({}, {
                    form_url: form_url,
                    data_url: data_url,
                    map: this._map
                }),
                _that = this;
            this.feature_layers.add(feature_layer);

            // When markers have been added, fit the maps bounds based on all
            // feature layers
            feature_layer.on('layer_add_complete', function () {
                var bounds = L.latLngBounds([]);
                _that.feature_layers.each(function (feature_layer) {
                    bounds.extend(feature_layer.feature_group.getBounds());
                });
                _that._map.fitBounds(bounds);
            });
        }
    });

    // #### Determine the default layer from the specified list
    FH.Map.determineDefaultLayer = function (base_layers, language_code) {
        var custom_layer, lang_specific_layer, first;

        // Find the layer defined as custom, if any.
        custom_layer = _.find(base_layers, function (layer) {
            return layer.is_custom === true;
        });

        // Find the language specific layer if any.
        lang_specific_layer = _.find(base_layers, function (layer) {
            return layer.lang === language_code;
        });

        // Finally return the custom layer, language specific layer or the first
        // layer if non of the above exists.
        if (custom_layer) {
            return custom_layer;
        } else if (lang_specific_layer) {
            return lang_specific_layer;
        } else {
            return _.values(base_layers)[0];
        }
    };

    // A `FeatureLayer` is initialised with a form url and a data url. It loads
    // the form and then the geopoint data on initialization.
    var FeatureLayer = FH.FeatureLayer = Backbone.Model.extend({
        initialize: function (attributes, options) {
            var form,
                data,
                _that = this;

            this._map = options.map;
            // Save the form and data urls for later
            this.form_url = options.form_url;
            this.data_url = options.data_url;

            // Create the feature group that will manage our markers
            this.feature_group = new L.FeatureGroup()
                .addTo(this._map);

            // Initialize the form and geopoint data
            this.form = form = new FH.Form({}, {url: this.form_url});
            form.load();
            form.on('load', function () {
                // Get the list of GPS type questions to load GPS data first
                var gps_question = form.questionsByType(FH.types.GEOLOCATION)
                    // Extract the first gps question
                    .slice(0, 1)
                    .map(function (q) {
                        return q.get(FH.constants.NAME);
                    });

                _that.data = data = new FH.DataSet([], {url: _that.data_url});
                _that.on('gps_data_load', _that.onGPSData);
                data.load({fields: gps_question});
                data.on('load', function () {
                    _that.trigger('gps_data_load', gps_question[0]);
                });
            });
        },

        onGPSData: function (gps_field) {
            var _that = this;
            // Clear any markers within the feature group
            this.feature_group.clearLayers();
            this.data.each(function (record) {
                var gps_string = record.get(gps_field),
                    latLng,
                    marker;
                if (gps_string) {
                    latLng = FH.FeatureLayer.parseLatLngString(gps_string);
                    //try{
                    marker = L.circleMarker(latLng, {
                        color: '#fff',
                        border: 8,
                        fillColor: '#ff3300',
                        fillOpacity: 0.9,
                        radius: 8,
                        opacity: 0.5
                    });
                    /*}
                    catch (e) {
                        console.error(e);
                    }*/
                    _that.feature_group.addLayer(marker);
                }
            });
            // Trigger event to notify that this layer is complete -> to be
            // caught by the `FeatureLayerSet` or `FHMap` to zoom to contain
            // all markers
            this.trigger('layer_add_complete');
        }
    });

    // Take a string in the form "lat lng alt precision" and return an array
    // with lat and lng for leaflet's consumption
    FH.FeatureLayer.parseLatLngString = function (lat_lng_str) {
        return lat_lng_str
            .split(" ")
            .slice(0, 2)
            .map(function (d) {
                return parseFloat(d);
            });
    };

    // A `FeatureLayerSet` contains a number of `FeatureLayers` that available
    // on the map
    var FeatureLayerSet = FH.FeatureLayerSet = Backbone.Collection.extend({
        model: FeatureLayer
    });

    // Leaflet shortcuts for common tile providers - is it worth adding such 1.5kb to Leaflet core?
    // https://gist.github.com/mourner/1804938
    var osmAttr = '&copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>';

    L.TileLayer.Common = L.TileLayer.extend({
        initialize: function (options) {
            L.TileLayer.prototype.initialize.call(this, this.url, options);
        }
    });

    L.TileLayer.CloudMade = L.TileLayer.Common.extend({
        url: 'http://{s}.tile.cloudmade.com/{key}/{styleId}/256/{z}/{x}/{y}.png',
        options: {
            attribution: 'Map data ' + osmAttr + ', Imagery &copy; <a href="http://cloudmade.com">CloudMade</a>',
            styleId: 997
        }
    });

    L.TileLayer.OpenStreetMap = L.TileLayer.Common.extend({
        url: 'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        options: {attribution: osmAttr}
    });

    L.TileLayer.OpenCycleMap = L.TileLayer.Common.extend({
        url: 'http://{s}.tile.opencyclemap.org/cycle/{z}/{x}/{y}.png',
        options: {
            attribution: '&copy; OpenCycleMap, ' + 'Map data ' + osmAttr
        }
    });

    L.TileLayer.MapBox = L.TileLayer.Common.extend({
        url: 'https://{s}.tiles.mapbox.com/v3/{user}.{map}/{z}/{x}/{y}.png'
    });

    L.TileLayer.Google = function (options) {
        return new L.Google(options.type, options);
    };

    L.TileLayer.Generic = function (options) {
        return new L.TileLayer(options.url, options);
    };

    // Assign functions that instantiate the different types of layers
    LayerFactories[FH.layers.MAPBOX] = L.TileLayer.MapBox;
    LayerFactories[FH.layers.CLOUD_MADE] = L.TileLayer.CloudMade;
    LayerFactories[FH.layers.OPEN_STREET_MAP] = L.TileLayer.OpenStreetMap;
    LayerFactories[FH.layers.OPEN_CYCLE_MAP] = L.TileLayer.OpenCycleMap;
    LayerFactories[FH.layers.GOOGLE] = L.TileLayer.Google;
    LayerFactories[FH.layers.GENERIC] = L.TileLayer.Generic;
}).call(this);

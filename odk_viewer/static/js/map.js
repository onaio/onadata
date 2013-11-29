// FH.Map Closure
// ------------------
(function () {
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
        // Colors we pop from whenever we add a a new layer and push to when
        // we remove
        markerColors: ["#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#e41a1c"],
        // #### Initialize the map
        // Called when a new map is constructed, we initialize the leaflet map
        // here.
        initialize: function (options) {
            var default_layer_config,
                _that = this;

            this.options = options || {};

            // Populate un-specified options with defaults
            _.defaults(this.options, defaults);

            // Create the layers control
            this._layersControl = new L.Control.Layers();

            // Initialize the leaflet `_map` and assign it as a property of this
            // FH.Map instance
            this._map = L.map(this.el, {
                zoom: this.options.zoom,
                center: this.options.center
            }).addControl(this._layersControl);

            // Create the FeatureLayerSet
            this.featureLayers = new FH.FeatureLayerSet();

            // Create feature layer's container
            this.$featureLayersContainer = $('<div class="feature-layers-container"></div>');
            this.$('.leaflet-bottom.leaflet-left').append(this.$featureLayersContainer);

            // Listen for `add` events to add the feature to the map
            this.featureLayers.on('add', function (featureLayer) {
                featureLayer.featureGroup.addTo(_that._map);

                // When markers have been added, fit the maps bounds based on all
                // feature layers
                featureLayer.on('markersCreated', function () {
                    _that.reCalculateBounds();
                });

                // Listen to `markerClicked` events from the feature
                featureLayer.on('markerClicked', function (record) {
                    // Update the data view's model
                    featureLayer.dataView.setModel(record);
                    _that.dataModal.render(featureLayer.dataView.$el, record);
                });

                // Add the layer's controls to the page
                _that.$featureLayersContainer.append(featureLayer.layerView.$el);
            });

            // Listen for `remove` events to remove the feature from the map
            this.featureLayers.on('remove', function (featureLayer) {
                // TODO: HACK
                _that.markerColors.push(featureLayer.fillColor);

                // Remove the layer's view from the page
                featureLayer.layerView.remove();

                _that._map.removeLayer(featureLayer.featureGroup);
                _that.reCalculateBounds();
            });

            // Create a `DataModal` instance to manage the data modal
            this.dataModal = new FH.DataModal({el: '#enketo-modal'});

            // determine the default layer
            default_layer_config = FH.Map.determineDefaultLayer(this.options.layers);

            // Add base layers that were defined within options
            this.options.layers.forEach(function (layer_config) {
                // is this layer the we determined to be our default
                var is_default = default_layer_config === layer_config;
                _that.addBaseLayer(layer_config, is_default);
            });
        },

        reCalculateBounds: function () {
            var bounds = L.latLngBounds([]);
            this.featureLayers.each(function (layer) {
                bounds.extend(layer.featureGroup.getBounds());
            });
            this._map.fitBounds(bounds);
        },

        // #### Add a base layer
        // The map must already be initialised
        addBaseLayer: function (layer_config, is_default) {
            // If type is not defined, set it to generic.
            layer_config.type = layer_config.type || FH.layers.GENERIC;

            // Call the appropriate function to instantiate a layer of this type.
            var layer = new LayerFactories[layer_config.type](layer_config.options);

            // Add the layer to the layer's control.
            this._layersControl.addBaseLayer(layer, layer_config.label);

            // If the is_default flag is set, add it to the map.
            if (is_default) {
                this._map.addLayer(layer);
            }
            return layer;
        },

        // Specify a form_url, data_url and optionally marker styles to create
        // and add a new feature/marker layer
        addFeatureLayer: function (form_url, data_url, options) {
            options = options || {};
            // TODO: HACK
            var markerColor = this.markerColors.pop();
            options.markerStyle = options.markerStyle || {};
            options.markerStyle.color = markerColor;
            // TODO: End HACK

            return this.featureLayers.createFeatureLayer(
                form_url, data_url, options);
        }
    });

    // Determine the default layer from the specified list
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
    // the form and then the geo data on initialization.
    var FeatureLayer = FH.FeatureLayer = Backbone.Model.extend({
        // The leaflet `FeatureGroup` that contains this layer's markers
        featureGroup: void 0,

        // Our id is determined by the form's url
        idAttribute: 'form_url',

        // The default style to be applied to the marker, override by providing
        // a `markerStyle` object within options on initialization
        markerStyle: {
            color: '#ff3300',
            border: 8,
            fillColor: '#fff',
            fillOpacity: 0.9,
            radius: 8,
            opacity: 0.5
        },

        // FH Datavore wrapper
        datavoreWrapper: void 0,

        initialize: function (attributes, options) {
            var form,
                data,
                _that = this;

            if (!this.get('form_url')) {
                throw new Error("You must specify the form's url");
            }

            if (!this.get('data_url')) {
                throw new Error("You must specify the data url");
            }

            // TODO: HACK - Store the marker color
            this.fillColor = options.markerStyle.fillColor;

            // Setup our marker style by extending the default `makerStyle`
            // with the provided style - if any
            _.extend(this.markerStyle, options.markerStyle);

            // Create the feature group that will contain our markers
            this.featureGroup = new L.FeatureGroup();

            this.featureGroup.on('click', function (evt) {
                var record = evt.layer._fh_data;
                if (!record) {
                    throw new Error("Marker layer does not have a record attached");
                }
                // Trigger a marker clicked event to be handled by the map
                _that.trigger('markerClicked', record);
            });

            // Initialize the `DataView`
            this.dataView = new FH.DataView();

            // Initialize the form and geo data
            this.form = form = new FH.Form({}, {url: this.get('form_url')});

            // Set this layers language to the first language in the list if any
            form.on('change:languages', function (model, value) {
                _that.set('language', value.slice(0, 1)[0]);
            }, this);

            // Set the language to a default value to force the change event
            // when the new value is `undefined` as it is for non-multilingual
            // forms
            this.set('language', '------');

            // Anytime the language changes, re-create the dataView's template
            // This assumes we have a valid form, which should be since the
            // language change is only triggered when the form is loaded
            this.on('change:language', function (model, language) {
                if (this.form.fields.length === 0) {
                    throw new Error("Triggered language change without having a valid form");
                }
                this.dataView.renderTemplate(this.form.fields, language);
            });

            // Re-build our layer view's field list whenever the forms fields change
            form.on('change:children', function () {
                this.layerView.render(this);
            }, this);

            form.load();
            form.on('load', function () {
                // Get the list of GPS type questions to load GPS data first
                var gpsQuestions = form.questionsByType(FH.types.GEOLOCATION)
                    // TODO: For now we are grabbing the the first geo question. In future we might expand this to allow the user to specify the question to map
                    .slice(0, 1)
                    .map(function (q) {
                        return q.get(FH.constants.XPATH);
                    });

                _that.data = data = new FH.DataSet([], {url: _that.get('data_url')});
                data.on('load', function () {
                    _that.createMarkers(gpsQuestions[0]);

                    // Disable this callback - infinite loop bad
                    data.off('load');

                    // load the rest of the data
                    data.on('load', function(){
                        // TODO: Enable the view for this feature layer here

                        // Initilaise the Dtavore wrapper
                        _that.datavoreWrapper = new FH.DatavoreWrapper(
                            {fieldSet: form.fields, dataSet: data});
                    });
                    data.load();
                });
                data.load({fields: gpsQuestions});
            });

            // Create our layer's view
            this.layerView = new FH.FeatureLayerView({featureLayer: this});
            this.layerView.on('fieldSelected', function (field) {
                var groups,
                    choices,
                    chromaScale;
                if(!this.datavoreWrapper) {
                    throw new Error("The Datavore wrapper must have been initialised");
                }
                // Group by the selected field
                groups = this.datavoreWrapper.countBy(field.id);
                chromaScale = chroma.scale('Set3').domain([0, groups.length - 1]).out('hex');
                choices = _.map(groups, function (g, idx) {
                    return {id: g.key, title: g.key, count: g.value, color: chromaScale(idx)};
                });
                this.layerView.render(this, field.cid, choices);

                // Update markers
                this.featureGroup.eachLayer(function (layer) {
                    // Get the value for this field for the submission in this layer
                    var match,
                        value = layer._fh_data.get(field.get('xpath'));

                    // Find the match and thus the color within choices
                    match = _.find(choices, function (choice) {
                        return choice.id === value;
                    });
                    layer.setStyle({
                        color: '#fff',
                        border: 8,
                        fillColor: match.color,
                        fillOpacity: 0.9,
                        radius: 8,
                        opacity: 0.5
                    });
                });
            }, this);
        },

        createMarkers: function (gps_field) {
            var _that = this;
            // Clear any markers within the feature group
            this.featureGroup.clearLayers();
            this.data.each(function (record) {
                var gps_string = record.get(gps_field),
                    latLng,
                    marker;
                if (gps_string) {
                    latLng = FH.FeatureLayer.parseLatLngString(gps_string);
                    //try{
                    marker = L.circleMarker(latLng, _that.markerStyle);
                    /*}
                     catch (e) {
                     //console.error(e);
                     }*/
                    // Attach the data to be used on marker clicks
                    marker._fh_data = record;
                    _that.featureGroup.addLayer(marker);
                }
            });
            // Trigger `markersCreated` event to notify that this layer is
            // complete -> to be caught by the `FHMap` to fit bounds
            this.trigger('markersCreated');
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

    // Displays and allows interaction to manipulate a `FeatureLayer`'s state
    FH.FeatureLayerView = Backbone.View.extend({
        className: 'feature-layer leaflet-control',
        template: _.template('<h3><%= layer.title %></h3>' +
            '<div>' +
              '<select class="field-selector">' +
                '<option value="">--None--</option>' +
                '<% _.each(layer.fields, function(field){ %>' +
                  '<option value="<%= field.cid %>" <% if(field.cid === layer.fieldCID){ %> selected="" <% } %>><%= field.label %></option>' +
                '<% }); %>' +
              '</select>' +
            '</div>' +
            '<% if(layer.fieldCID){ %>' +
              '<div class="legend">' +
                '<ul class="nav nav-pills nav-stacked">' +
                  '<% _.each(layer.choices, function(choice){ %>' +
                    '<li>' +
                      '<a href="javascript:;" rel="">' +
                        '<span class="legend-bullet" style="background-color: <%= choice.color %>;"></span>' +
                        '<span class="legend-response-count"><%= choice.count %></span>' +
                        '<span class="item-label language"><%= choice.title || "Not Specified" %></span>' +
                      '</a>' +
                    '</li>' +
                  '<% }); %>' +
                '</ul' +
              '</div>' +
            '<% } %>'),
        events: {
            "change .field-selector": "fieldSelected"
        },

        initialize: function (options) {
            if( !options.featureLayer ) {
                throw new Error("You must specify this view's feature layer on initialization.");
            }
            this.featureLayer = options.featureLayer;
        },

        render: function (featureLayer, fieldCID, choices) {
            var data,
                fields,
                _that = this;

            fieldCID = fieldCID || "";
            choices = choices || [];
            fields = featureLayer.form.questionsByType(FH.types.SELECT_ONE)
                .map(function (field) {
                    return {
                        cid: field.cid,
                        label: field.get('label', _that.featureLayer.get('language'))
                    };
                });
            data = {
                title: featureLayer.form.get('title'),
                fields: fields,
                fieldCID: fieldCID,
                choices: choices
            };
            this.$el.html(this.template({layer: data}));
        },

        fieldSelected: function (evt) {
            var cid = evt.target.value,
                targetField;
            // Find the field by this cid
            targetField = this.featureLayer.form.fields.find(function (field) {
                return field.cid === cid;
            });
            if(targetField) {
                // trigger field selected
                this.trigger('fieldSelected', targetField);
            }
        }
    });

    // A `FeatureLayerSet` contains a number of `FeatureLayers` that are
    // available on the map
    FH.FeatureLayerSet = Backbone.Collection.extend({
        model: FeatureLayer,

        // Convenience method to create a `FeatureLayer`
        createFeatureLayer: function (form_url, data_url, options) {
            var featureLayer;

            options = options || {};
            featureLayer = new FeatureLayer({
                form_url: form_url,
                data_url: data_url
            }, options);
            this.add(featureLayer);
            return featureLayer;
        }
    });

    // View used to render data per `FeatureLayer`, its template is compiled
    // on init, based on the specified fields
    FH.DataView = Backbone.View.extend({
        // Don't set directly as we need to do some cleanup on set
        model: void 0,

        render: function () {
            // Allow graceful rendering model has not been set
            var data = this.model && this.model.toJSON() || {};
            this.$el.html(this.template({record: data}));
        },

        renderStatus: function (message) {
            this.$el.html(message);
        },

        // Render the current model to our template using the specified form
        // `FieldSet`
        renderTemplate: function (fieldSet, language) {
            this.template = _.template(FH.DataView.templateFromFields(fieldSet, language));
            // Re-render in-case we are in view
            this.render();
            return this;
        },

        // Set/Get the views model, used to disable any pending events
        setModel: function (record) {
            if (this.model) {
                this.model.off('ready');
            }
            this.model = record;
            this.model.on('ready', this.render, this);
            this.model.on('readyFailed', function () {
                this.renderStatus("Failed to load ...");
            }, this);

            // set us to loading
            this.renderStatus("Loading ...");

            // Initiate the load
            this.model.load();
        }
    });

    // Create an underscore template based on a forms fields
    FH.DataView.templateFromFields = function (fields, language) {
        var template_string = '<table class="table table-bordered table-striped">';
        template_string += '<tr><th>Question</th><th>Response</th></tr>';
        fields.each(function (f) {
            template_string += '<tr>';
            template_string += '<td>' + f.get('label', language) + '</td>';
            template_string += '<td><%= record["' + f.get('xpath') + '"] %></td>';
            template_string += '</tr>';
        });
        template_string += '</table>';
        return template_string;
    };

    FH.DataModal = Backbone.View.extend({
        render: function (elm, record) {
            // Clear current contents and append new
            this.$('.inner-modal').empty().append(elm);
            this.$el.modal();
        }
    });

    // COLORS MODULE
    FH.Colors = (function() {
        var colors = {};
        var colorschemes = {proportional: {
            // http://colorbrewer2.org/index.php?type=sequential
            "Set1": ["#EFEDF5", "#DADAEB", "#BCBDDC", "#9E9AC8", "#807DBA", "#6A51A3", "#54278F", "#3F007D"],
            "Set2": ["#DEEBF7", "#C6DBEF", "#9ECAE1", "#6BAED6", "#4292C6", "#2171B5", "#08519C", "#08306B"]
        }};
        var defaultColorScheme = "Set1";
        function select_from_colors(type, colorscheme, zero_to_one_inclusive) {
            var epsilon = 0.00001;
            colorscheme = colorscheme || defaultColorScheme;
            var colorsArr = colorschemes[type][colorscheme];
            return colorsArr[Math.floor(zero_to_one_inclusive * (colorsArr.length - epsilon))];
        }

        // METHODS FOR EXPORT
        colors.getNumProportional = function(colorscheme) {
            colorscheme = colorscheme || defaultColorScheme;
            return colorschemes.proportional[colorscheme].length;
        };
        colors.getProportional = function(zero_to_one, colorscheme) {
            return select_from_colors('proportional', colorscheme, zero_to_one);
        };

        return colors;
    }());

    FH.Colors.GetRandomColor = function (step, numOfSteps) {
        // This function generates vibrant, "evenly spaced" colours (i.e. no clustering). This is ideal for creating easily distiguishable vibrant markers in Google Maps and other apps.
        // Adam Cole, 2011-Sept-14
        // HSV to RBG adapted from: http://mjijackson.com/2008/02/rgb-to-hsl-and-rgb-to-hsv-color-model-conversion-algorithms-in-javascript
        var r, g, b;
        var h = step / numOfSteps;
        var i = ~~(h * 6);
        var f = h * 6 - i;
        var q = 1 - f;
        switch(i % 6){
            case 0: r = 1, g = f, b = 0; break;
            case 1: r = q, g = 1, b = 0; break;
            case 2: r = 0, g = 1, b = f; break;
            case 3: r = 0, g = q, b = 1; break;
            case 4: r = f, g = 0, b = 1; break;
            case 5: r = 1, g = 0, b = q; break;
        }
        var c = "#" + ("00" + (~ ~(r * 255)).toString(16)).slice(-2) + ("00" + (~ ~(g * 255)).toString(16)).slice(-2) + ("00" + (~ ~(b * 255)).toString(16)).slice(-2);
        return (c);
    };

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

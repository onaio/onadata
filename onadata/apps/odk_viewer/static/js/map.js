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
                fhMap = this;

            this.options = options || {};

            // Populate un-specified options with defaults
            _.defaults(this.options, defaults);

            // Create the layers control
            this._layersControl = new L.Control.Layers();

            // Initialize the leaflet `_map` and assign it as a property of this
            // FH.Map instance
            this._map = L.map(this.el, {
                zoom: this.options.zoom,
                center: this.options.center,
                zoomControl: false
            })
                .addControl(L.control.zoom({position: 'topright'}))
                .addControl(this._layersControl);

            // Create the FeatureLayerSet
            this.featureLayers = new FH.FeatureLayerSet();

            // Create feature layer's container
            this.$featureLayersContainer = $('<div class="feature-layers-container"></div>');
            this.$('.leaflet-top.leaflet-left').append(this.$featureLayersContainer);

            // Listen for `add` events to add the feature to the map
            this.featureLayers.on('add', function (featureLayer) {
                featureLayer.featureGroup.addTo(fhMap._map);

                // When markers have been added, fit the maps bounds based on all
                // feature layers
                featureLayer.on('markersCreated', function () {
                    fhMap.reCalculateBounds();
                });

                // Listen to `markerClicked` events from the feature
                featureLayer.on('markerClicked', function (record) {
                    // Update the data view's model
                    featureLayer.dataView.setModel(record);
                    featureLayer.dataModal.render(featureLayer.dataView.$el, record);
                });

                // Add the layer's controls to the page
                fhMap.$featureLayersContainer.append(featureLayer.layerView.$el);
            });

            // Listen for `remove` events to remove the feature from the map
            this.featureLayers.on('remove', function (featureLayer) {
                // TODO: HACK
                fhMap.markerColors.push(featureLayer.fillColor);

                // Remove the layer's view from the page
                featureLayer.layerView.remove();

                fhMap._map.removeLayer(featureLayer.featureGroup);
                fhMap.reCalculateBounds();
            });

            // determine the default layer
            default_layer_config = FH.Map.determineDefaultLayer(this.options.layers);

            // Add base layers that were defined within options
            this.options.layers.forEach(function (layer_config) {
                // is this layer the we determined to be our default
                var is_default = default_layer_config === layer_config;
                fhMap.addBaseLayer(layer_config, is_default);
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
        addFeatureLayer: function (formUrl, dataUrl, enketoEditUrl, enketoAddUrl, deleteAPIUrl, options) {
            options = options || {};
            // TODO: HACK
            var markerColor = this.markerColors.pop();
            options.markerStyle = options.markerStyle || {};
            options.markerStyle.color = markerColor;
            // TODO: End HACK

            return this.featureLayers.createFeatureLayer(
                formUrl, dataUrl, enketoEditUrl, enketoAddUrl, deleteAPIUrl, options);
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

        // Currently active list of choices
        currentViewByChoices: void 0,

        // The currently active view-by field
        selectedViewByField: void 0,

        // Currently selected list of choices
        selectedViewByChoices: [],

        initialize: function (attributes, options) {
            var form,
                data,
                fhFeatureLayer = this;

            if (!this.get('form_url')) {
                throw new Error("You must specify the form's url");
            }

            if (!this.get('data_url')) {
                throw new Error("You must specify the data url");
            }

            if (!this.get('enketoEditUrl')) {
                throw new Error("You must specify the Enketo Edit url");
            }

            if (!this.get('enketoAddUrl')) {
                throw new Error("You must specify the Enketo Add url");
            }

            if (!this.get('deleteAPIUrl')) {
                throw new Error("You must specify the Delete API url");
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
                fhFeatureLayer.trigger('markerClicked', record);
            });

            // Initialize the `DataView`
            this.dataView = new FH.DataView();

            // Create our layer's view
            this.layerView = new FH.FeatureLayerView({featureLayer: this});

            // Initialize the form and geo data
            this.form = form = new FH.Form({}, {url: this.get('form_url')});

            // An `EnketoIFrame`
            this.enketoIFrame = new FH.EnketoIFrame({editUrlTpl: this.get('enketoEditUrl')});

            // Create a `DataModal` instance to manage the data modal
            this.dataModal = new FH.DataModal({el: '#enketo-modal'});

            // Delete confirmation modal
            this.deleteModal = new FH.DeleteModal({el: '#delete-modal'});

            this.dataModal.on('editRequested', function (dataID) {
                this.enketoIFrame.render(dataID);
                this.dataModal.render(this.enketoIFrame.$el);
            }, this);

            this.dataModal.on('deleteRequested', function (dataID) {
                // Hide the DataModal
                this.dataModal.$el.modal('hide');
                this.deleteModal.render(dataID);
            }, this);


            this.deleteModal.on('deleteConfirmed', function (dataID){
                // Find the record
                var xhr,
                    record = this.data.find(function (data) {
                        return data.id === dataID;
                    });
                if (record) {
                    record.on('destroy', function (record, collection, xhr) {
                        // Remove marker from the map
                        var layer = _.find(this.featureGroup.getLayers(), function(layer, id){return layer._fh_data.id === record.id})
                        this.featureGroup.removeLayer(layer && layer._leaflet_id);
                    }, this);
                    xhr = record.destroy({url: this.get('deleteAPIUrl'), data: 'id=' + dataID});
                }
                // Close both delete and data modals
                this.deleteModal.$el.modal('hide');
                this.dataModal.$el.modal('hide');
            }, this);

            this.deleteModal.on('deleteCanceled', function (dataID) {
                // Hide the DataModal
                this.dataModal.$el.modal('show');
            }, this);

            // Set this layers language to the first language in the list if any
            form.on('change:languages', function (model, value) {
                var currentLanguage = value.slice(0, 1)[0];
                fhFeatureLayer.set('languages', value);
                fhFeatureLayer.set('language', currentLanguage);

                // TODO: we should probably re-render the layerView if this change happens anywhere other than on initial load
            }, this);

            // Set the language to a default value to force the change event
            // when the new value is `undefined` as it is for non-multilingual
            // forms
            this.set({'language': '------'}, {silent: true});

            // Anytime the language changes, re-create the dataView's template
            // This assumes we have a valid form, which should be since the
            // language change is only triggered when the form is loaded
            this.on('change:language', function (model, language) {
                if (this.form.fields.length === 0) {
                    throw new Error("Triggered language change without having a valid form");
                }
                this.dataView.renderTemplate(this.form, language);

                // Update the layer view
                this.layerView.render(this);
            });

            // Catch layer view's language change events and propagate to change:language
            this.layerView.on('languageChanged', function (newLanguage) {
                this.set('language', newLanguage);
            }, this);

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

                fhFeatureLayer.data = data = new FH.DataSet([], {url: fhFeatureLayer.get('data_url')});
                data.on('load', function () {
                    // TODO: We might get here without any records, `markersCreated` then throws
                    fhFeatureLayer.createMarkers(gpsQuestions[0]);

                    // Disable this callback - infinite loop bad
                    data.off('load');

                    // load the rest of the data
                    data.on('load', function(){
                        // Initialize the Datavore wrapper
                        fhFeatureLayer.datavoreWrapper = new FH.DatavoreWrapper(
                            {fieldSet: form.fields, dataSet: data});
                    });
                    data.load();
                });
                data.load({fields: gpsQuestions});
            });

            this.layerView.on('fieldSelected', function (field) {
                var groups,
                    chromaScale,
                    featureLayer = this,
                    children;

                if(!this.datavoreWrapper) {
                    throw new Error("The Datavore wrapper must have been initialised");
                }

                this.selectedViewByField = field;
                // Group by the selected field
                groups = this.datavoreWrapper.countBy(field.id);
                chromaScale = chroma.scale('Set3').domain([0, Math.max(groups.length - 1, 1)]).out('hex');

                this.currentViewByChoices = _.map(groups, function (g, idx) {
                    var choice = _.find(field.get(FH.constants.CHILDREN), function (c) {
                        return c.name === g.key;
                    });
                    // Turn the choice into an FH.Field so we can make use of the multi-lang feature
                    return {field: new FH.Field(choice), count: g.value, color: chromaScale(idx)};
                });
                this.layerView.render(this);

                // Update markers
                this.featureGroup.eachLayer(function (layer) {
                    // Get the value for this field for the submission in this layer
                    var match,
                        value = layer._fh_data.get(field.get('xpath'));

                    // Find the match and thus the color within choices
                    match = _.find(featureLayer.currentViewByChoices, function (choice) {
                        return choice.field.get(FH.constants.NAME) === value;
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

            this.layerView.on('choicesChanged', function (selectedChoices) {
                // Check if we have any choices, if not show everything
                var fhFeatureLayer = this;

                if (selectedChoices.length > 0) {
                    this.featureGroup.eachLayer(function (layer) {
                        var style,
                            opacity,
                            response = layer._fh_data.get(fhFeatureLayer.selectedViewByField.get('xpath'));
                        // If response is not one of the choices, set its opacity
                        if( _.indexOf(selectedChoices, response) > -1 ) {
                            opacity = 0.9;
                        } else {
                            opacity = 0.2;
                        }
                        style = {
                            color: layer.options.color,
                            border: layer.options.border,
                            fillColor: layer.options.fillColor,
                            fillOpacity: layer.options.fillOpacity,
                            radius: layer.options.radius,
                            opacity: layer.options.opacity
                        };
                        style.fillOpacity = style.opacity = opacity;
                        layer.setStyle(style);
                    });
                } else {
                    this.featureGroup.eachLayer(function (layer) {
                        var style = {
                            color: layer.options.color,
                            border: layer.options.border,
                            fillColor: layer.options.fillColor,
                            fillOpacity: layer.options.fillOpacity,
                            radius: layer.options.radius,
                            opacity: layer.options.opacity
                        };

                        // Set every layer's opacity to full
                        style.fillOpacity = style.opacity = 0.9;
                        layer.setStyle(style);
                    });
                }
            }, this);
        },

        createMarkers: function (gps_field) {
            var fhFeatureLayer = this;
            // Clear any markers within the feature group
            this.featureGroup.clearLayers();
            this.data.each(function (record) {
                var gps_string = record.get(gps_field),
                    latLng,
                    marker;
                if (gps_string) {
                    latLng = FH.FeatureLayer.parseLatLngString(gps_string);
                    //try{
                    marker = L.circleMarker(latLng, fhFeatureLayer.markerStyle);
                    /*}
                     catch (e) {
                     //console.error(e);
                     }*/
                    // Attach the data to be used on marker clicks
                    marker._fh_data = record;
                    fhFeatureLayer.featureGroup.addLayer(marker);
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
            '<% if(layer.languages.length > 0){ %>' +
              '<h4>Language</h4>' +
              '<div>' +
                '<select class="language-selector">' +
                  '<% _.each(layer.languages, function(lang){ %>' +
                    '<option value="<%= lang %>" <% if(lang === layer.currentLang){ %> selected="" <% } %>><%= lang %></option>' +
                  '<% }); %>' +
                '</select>' +
              '</div>' +
            '<% } %>' +
            '<div>' +
              '<h4>View By</h4>' +
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
                      '<a href="javascript:;" rel="" data-choice="<%= choice.id %>" class="legend-label">' +
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
            "change .field-selector": "fieldSelected",
            "click ul.nav li a": "choiceClicked",
            "change .language-selector": "languageChanged"
        },

        initialize: function (options) {
            if( !options.featureLayer ) {
                throw new Error("You must specify this view's feature layer on initialization.");
            }
            this.featureLayer = options.featureLayer;
        },

        render: function (featureLayer) {
            var data,
                fields,
                fieldCID,
                choices,
                fhFeatureLayerView = this;

            fieldCID = featureLayer.selectedViewByField && featureLayer.selectedViewByField.cid || "";
            choices = _.map(featureLayer.currentViewByChoices, function (choice) {
                return {id: choice.field.get('name'), title: choice.field.get('label', featureLayer.get('language')), count: choice.count, color: choice.color};
            });
            fields = featureLayer.form.questionsByType(FH.types.SELECT_ONE)
                .map(function (field) {
                    return {
                        cid: field.cid,
                        label: field.get('label', featureLayer.get('language'))
                    };
                });
            data = {
                title: featureLayer.form.get('title'),
                fields: fields,
                fieldCID: fieldCID,
                choices: choices,
                languages: featureLayer.get('languages') || [],
                currentLang: featureLayer.get('language') || void 0
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
        },

        choiceClicked: function (evt) {
            var $target = $(evt.currentTarget),
                choice;
            choice = $target.data('choice');

            // Toggle the choices active state
            $target.hasClass('active')?$target.removeClass('active'):$target.addClass('active');

            // Get list of active choices
            this.trigger(
                'choicesChanged',
                _.map(this.$el.find('a.active'), function (el) {
                    // If choice is an empty string, return undefined
                    return $(el).data('choice') || undefined;
                })
            );
        },

        languageChanged: function (evt) {
            var $target = $(evt.currentTarget);

            this.trigger('languageChanged', $target.val());
        }
    });

    // A `FeatureLayerSet` contains a number of `FeatureLayers` that are
    // available on the map
    FH.FeatureLayerSet = Backbone.Collection.extend({
        model: FeatureLayer,

        // Convenience method to create a `FeatureLayer`
        createFeatureLayer: function (formUrl, dataUrl, enketoEditUrl, enketoAddUrl, deleteAPIUrl, options) {
            var featureLayer;

            options = options || {};
            featureLayer = new FeatureLayer({
                form_url: formUrl,
                data_url: dataUrl,
                enketoEditUrl: enketoEditUrl,
                enketoAddUrl: enketoAddUrl,
                deleteAPIUrl: deleteAPIUrl
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
        attributes: {
            class: 'inner-modal-content'
        },

        render: function () {
            // Allow graceful rendering when model has not been set
            var data = this.model && this.model.toJSON() || {};
            this.$el.html(this.template({record: data}));
            this.delegateEvents(this.events);
            return this;
        },

        renderStatus: function (message) {
            this.$el.html(message);
        },

        // Render the current model to our template using the specified form
        // `FieldSet`
        renderTemplate: function (form, language) {
            this.template = _.template(FH.DataView.templateFromFields(form.fields, language));
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
        // Render edit/delete buttons
        template_string += '' +
            '<ul>' +
              '<li>' +
                '<a class="edit-submission btn" data-id="<%= record["_id"] %>">Edit Submission Data</a>' +
              '</li>' +
              '<li>' +
                '<a class="del-submission btn btn-danger" data-id="<%= record["_id"] %>">Delete Submission</a>' +
              '</li>' +
            '</ul>';
        // Render attachments
        template_string += '' +
            '<% if (record["_attachments"] && record["_attachments"].length > 0) { %>' +
              '<ul class="media-grid">' +
                '<% _.each(record["_attachments"], function (a) { %>' +
                  '<li>' +
                    '<a href="/attachment/?media_file=<%= a %>" target="_blank">' +
                      '<img class="thumbnail" width="210" src="/attachment/?media_file=<%= a %>&size=small" />' +
                    '</a>' +
                  '</li>' +
                '<% }) %>' +
              '</ul>' +
            '<% } %>';
        fields.each(function (f) {
            template_string += '' +
                '<tr>' +
                  '<td>' + f.get('label', language) + '</td>' +
                  '<td><%= record["' + f.get('xpath') + '"] %></td>' +
                '</tr>';
        });
        template_string += '</table>';
        return template_string;
    };

    FH.EnketoIFrame = Backbone.View.extend({
        template: _.template('<iframe src="<%= data.url %>" scrolling="yes" marginwidth="0" marginheight="0" frameborder="0" vspace="0" hspace="0"></iframe>'),
        attributes: {
            class: 'inner-modal-content'
        },

        initialize: function (options) {
            this.editUrlTemplate = _.template(options.editUrlTpl);
        },

        render: function (dataID) {
            var data = {
                url: this.editUrlTemplate({id: dataID})
            };
            this.$el.html(this.template({data: data}));
        }
    });

    FH.DataModal = Backbone.View.extend({
        events: {
            "click .edit-submission": "editClicked",
            "click .del-submission": "deleteClicked"
        },
        attributes: {
            class: 'inner-modal-content'
        },

        render: function (elm, record) {
            // Clear current contents and append new
            this.$('.inner-modal').empty().append(elm);
            this.$el.modal();
        },

        editClicked: function (evt) {
            var $target = $(evt.currentTarget);
            this.trigger('editRequested', ($target.data('id')));
        },

        deleteClicked: function (evt) {
            var $target = $(evt.currentTarget);
            this.trigger('deleteRequested', ($target.data('id')));
        }
    });

    FH.DeleteModal = Backbone.View.extend({
        events: {
            'click a.secondary': function () {
                // Remove data ID set on delete button
                this.$('.btn-primary').data('id', "");
                this.trigger('deleteCanceled');
            },
            'click a.btn-primary': function (evt) {
                var $target = $(evt.currentTarget);
                // disable the button
                $target.addClass('disabled');
                this.trigger('deleteConfirmed', $target.data('id'));
            }
        },

        render: function (dataID) {
            var primaryBtn = this.$('.btn-primary');
            // Update data id on delete button
            primaryBtn.data('id', dataID);
            primaryBtn.removeClass('disabled');
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

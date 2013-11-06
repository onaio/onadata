// Formhub Map Component Specs
// ---------------------------
describe("Formhub Map", function () {
    // Handle to our map's DOM element
    var el;

    var layer_configs = [
        {label: 'Mapbox Streets', options: {user: 'modilabs', map: 'map-iuetkf9u'}},
        {label: 'MapBox Streets Light', options: {user: 'modilabs', map: 'map-p543gvbh'}},
        {label: 'MapBox Streets Zenburn', options: {user: 'modilabs', map: 'map-bjhr55gf'}},
        {label: 'Cloudless Earth', options: {user: 'modilabs', map: 'map-aef58tqo'}},
        {label: 'Mapbox Streets (Français)', options: {user: 'modilabs', map: 'map-vdpjhtgz'}, lang: 'fr'},
        {label: 'Mapbox Streets (Español)', options: {user: 'modilabs', map: 'map-5gjzjlah'}, lang: 'es'}
    ];
    var customMapBoxTileLayer = {
        label: 'Mapbox Street Custom',
        options: {
            url: 'http://{s}.tiles.mapbox.com/v3/modilabs.map-iuetkf9u.json',
            attribution: '&copy; Me'
        },
        is_custom: true
    };

    // Create a `#map` div before each spec and assign it to the `el` variable.
    beforeEach(function () {
        $('body').append($('<div id="map"></div>'));
        el = $('#map');
    });

    // Remove the `#map` div after each spec and un-define the `el` variable.
    afterEach(function () {
        el.remove();
        el = undefined;
    });

    // ### Test the map's initialization
    describe("Map initialization", function () {
        // Test that default map options are overridden when specified.
        it("overrides defaults", function () {
            var map = new FH.Map({
                el: el,
                zoom: 13,
                center: [36.0, -1.0]
            });
            expect(map.options.zoom).toEqual(13);
            expect(map.options.center).toEqual([36.0, -1.0]);
        });

        // Test that default map options are used if overrides are not specified.
        it("uses defaults if they are not specified", function () {
            var map = new FH.Map({
                el: el
            });
            expect(map.options.zoom).toEqual(8);
            expect(map.options.center).toEqual([0, 0]);
        });
    });

    // ### Test base layer functionality.
    describe("Base Layers", function () {
        it("creates base layers defined at initialisation", function () {
            var map = new FH.Map({
                el: el,
                layers: layer_configs.concat([customMapBoxTileLayer])
            });
            expect(_.keys(map._layersControl._layers).length).toEqual(7);
        });

        describe("Layer Initialisation by type", function () {
            var map;
            // Create an FH.Map before each spec
            beforeEach(function () {
                map = new FH.Map({
                    el: el
                });
            });

            // Test that `addBaseLayer` can add a MapBox layer
            it("can add a mapbox layer", function () {
                var mapbox_layer_config = {
                        type: FH.layers.MAPBOX,
                        label: 'Mapbox Streets',
                        options: {
                            user: 'modilabs',
                            map: 'map-iuetkf9u',
                            attribution: 'Map data (c) OpenStreetMap contributors, CC-BY-SA'
                        }
                    },
                    layer;
                layer = map.addBaseLayer(mapbox_layer_config, true);
                expect(map._map.hasLayer(layer)).toEqual(true);
            });

            // Test that `addBaseLayer` can add a Google layer
            it("can add a Google layer", function () {
                var google_layer_config = {
                        type: FH.layers.GOOGLE,
                        label: 'Google Hybrid',
                        options: {
                            type: 'HYBRID'
                        }
                    },
                    layer;
                layer = map.addBaseLayer(google_layer_config, true);
                expect(map._map.hasLayer(layer)).toEqual(true);
            });

            // Test that `addBaseLayer` can add a generic layer defined by url
            it("can add a generic layer", function () {
                var generic_layer_config = {
                        label: 'Custom Layer',
                        options: {
                            url: 'http://{s}.tiles.mapbox.com/v3/modilabs.map-iuetkf9u.json',
                            attribution: '&copy; Me'
                        }
                    },
                    layer;
                layer = map.addBaseLayer(generic_layer_config, true);
                expect(map._map.hasLayer(layer)).toEqual(true);
            });
        });
    });

    describe("determineDefaultLayer", function () {
        it("sets the custom layer as the default if its defined", function () {
            // add the custom layer
            var base_layers = layer_configs.concat([customMapBoxTileLayer]);
            var default_layer = FH.Map.determineDefaultLayer(base_layers, 'en');
            expect(default_layer).toBeDefined();
            expect(default_layer).toBe(customMapBoxTileLayer);
        });

        it("sets the layer matching the language code as the default if no custom layer is defined", function () {
            var default_layer = FH.Map.determineDefaultLayer(layer_configs, 'fr');
            expect(default_layer).toBeDefined();
            expect(default_layer.label).toEqual('Mapbox Streets (Français)');
        });

        it("sets the first defined layer as the default if no custom or language layer is found", function () {
            var default_layer = FH.Map.determineDefaultLayer(layer_configs, 'en');
            expect(default_layer).toBeDefined();
            expect(default_layer.label).toEqual('Mapbox Streets');
        });
    });
});

describe("FeatureLayer", function () {
    describe("parseLatLngString", function () {
        describe("valid string", function () {
            var lat_lng_str = "36.0 -1.2 3600 25",
                result;

            beforeEach(function () {
                result = FH.FeatureLayer.parseLatLngString(lat_lng_str);
            });

            it("returns an array with two elements", function () {
                expect(result.length).toEqual(2);
            });

            it("converts the string values into floats", function () {
                expect(typeof(result[0])).toEqual("number");
                expect(result[0]).not.toBeNaN();
            });
        });
    });
});

describe("DataView", function () {
    var fieldSet,
        raw_questions = [
            {
                name: "name",
                type: "text",
                label: "Name"
            },
            {
                name: "age",
                type: "integer",
                label: "Age"
            }
        ];

    beforeEach(function () {
        fieldSet = new FH.FieldSet();
        FH.Form.parseQuestions(raw_questions).forEach(function (field) {
            fieldSet.add(field);
        });
    });

    it("creates a template from the specified fieldSet", function () {
        var dataView = new FH.DataView({fieldSet: fieldSet});
        expect(dataView.template).toBeDefined();
    });

    describe("templateFromFields", function () {
        it("creates a table row for each question", function () {
            var result;

            result = FH.DataView.templateFromFields(fieldSet);
            expect(result).toEqual(
                '<table class="table table-bordered table-striped">' +
                    '<tr><th>Question</th><th>Response</th></tr>' +
                    '<tr><td>Name</td><td><%= record["name"] %></td></tr>' +
                    '<tr><td>Age</td><td><%= record["age"] %></td></tr>' +
                    '</table>');
        });
    });
});

EnvJasmine.load(EnvJasmine.mocksDir + "datalib.mock.js");
EnvJasmine.load(EnvJasmine.jsDir + "odk_viewer/static/js/datalib.js");

describe("Memory loader tests", function() {
    var reader, loader;

    beforeEach(function() {
        reader = new Reader();
        loader = new MemoryLoader(reader, data);
    });

    it("tests that load call works", function() {
        var deferred, loaded_data;

        runs(function(){
            deferred = loader.load();
        });

        waitsFor(function(){
            var done = false;
            deferred.done(function(mem_data){
                loaded_data = mem_data;
                done = true;
            });
            return done;
        }, "The promise callback to be called", 1000);

        runs(function() {
            expect(loaded_data).toBeDefined();
        });
    });
});

describe("Ajax loader tests", function() {
    var reader, loader;

    beforeEach(function() {
        reader = new Reader();
        loader = new AjaxLoader(reader, ajaxUrl);
        spyOn($, 'ajax').andCallFake(function() {
            var deferred = $.Deferred();
            deferred.resolve(data);
            return deferred;
        });
    });

    it("tests that load call works", function() {
        var deferred, loaded_data;

        runs(function(){
            deferred = loader.load();
        });

        waitsFor(function(){
            var done = false;
            deferred.done(function(ajax_data){
                loaded_data = ajax_data;
                done = true;
            });
            return done;
        }, "The promise callback to be called", 1000);

        runs(function() {
            expect(loaded_data).toBeDefined();
        });
    });
});

describe("Schema manager tests", function(){
    var reader, loader, schemaManager;

    beforeEach(function() {
        var deferred;
        reader = new Reader();
        loader = new MemoryLoader(reader, schema);
        schemaManager = new SchemaManager();

        runs(function(){
            deferred = schemaManager.init(loader);
        });

        waitsFor(function(){
            var done = false;
            deferred.done(function(data){
                done = true;
            });
            return done;
        }, "Schema manager to finish init", 1000);
    });

    it("checks that the schema was parsed", function(){
        expect(schemaManager.get("id_string")).toEqual("good_eats_other");
        expect(schemaManager._fields.length).toBeGreaterThan(0);
        expect(schemaManager.getFieldByName("location_photo").label()).toEqual("Served At");
        // TODO: test for other variations of geopoint field names
        expect(schemaManager.getFieldsByType(constants.GEOPOINT).length).toEqual(1);
        // check that we only have one language
        expect(schemaManager.getSupportedLanguages().length).toEqual(1);
        // check that options were setup
        expect(schemaManager.getFieldByName("food_type").options().length).toEqual(13);
    });
});

describe("Multi-lingual Schema manager tests", function(){
    var reader, loader, schemaManager;

    beforeEach(function() {
        var deferred;
        reader = new Reader();
        loader = new MemoryLoader(reader, multilang_schema);
        schemaManager = new SchemaManager();

        runs(function(){
            deferred = schemaManager.init(loader);
        });

        waitsFor(function(){
            var done = false;
            deferred.done(function(data){
                done = true;
            });
            return done;
        }, "Schema manager to finish init", 1000);
    });

    it("checks that the schema was parsed", function(){
        // check that we have 2 languages
        expect(schemaManager.getSupportedLanguages().length).toEqual(2);
        // check that a label() called without a language returns the default label
        expect(schemaManager.getFieldByName("location_photo").label()).toEqual("Served At Fr");
        // check that a label() called with a language returns the requested label
        expect(schemaManager.getFieldByName("location_photo").label("English")).toEqual("Served At");
        // check that options were setup
        expect(schemaManager.getFieldByName("food_type").options().length).toEqual(13);
    });
});

describe("DataManager tests", function(){
    var reader, dataLoader, schemaLoader, schemaManager, dataManager;

    beforeEach(function() {
        var deferred;
        reader = new Reader();
        schemaLoader = new MemoryLoader(reader, multilang_schema);
        schemaManager = new SchemaManager();
        dataLoader = new MemoryLoader(reader, data);
        dataManager = new DataManager(schemaManager);

        runs(function(){
            deferred = schemaManager.init(schemaLoader);
        });

        waitsFor(function(){
            var done = false;
            deferred.done(function(data){
                done = true;
            });
            return done;
        }, "Schema manager to finish init", 1000);

        runs(function(){
            deferred = dataManager.init(dataLoader)
        });

        waitsFor(function(){
            var done = false;
            deferred.done(function(data){
                done = true;
            });
            return done;
        }, "Data manager to finish loading", 1000);
    });

    it("checks that data was pushed to the store successfully", function(){
        var query = {"vals":[dv.count()]};
        // count the number of records
        //var result = dataManager.dvQuery(query);
        //expect(result[0][0]).toEqual(22);
    });
});
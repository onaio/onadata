describe("Memory loader tests", function() {
    var reader, loader;

    beforeEach(function() {
        reader = new fh.Reader();
        loader = new fh.MemoryLoader(reader, datalibMock.data);
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
        reader = new fh.Reader();
        loader = new fh.AjaxLoader(reader, datalibMock.ajaxUrl);
        spyOn($, 'ajax').andCallFake(function() {
            var deferred = $.Deferred();
            deferred.resolve(datalibMock.data);
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
        reader = new fh.Reader();
        loader = new fh.MemoryLoader(reader, datalibMock.schema);
        schemaManager = new fh.SchemaManager();

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

    it("checks that top level form attributes are set and can be retrieved by get", function(){
        expect(schemaManager.get("id_string")).toEqual("good_eats_other");
        expect(schemaManager.get("default_language")).toEqual("default");
    });

    it("tests getting all fields", function(){
        var fields = schemaManager.getFields();
        expect(fields.length).toEqual(13);
    });

    it("tests getting fields by name", function(){
        var foodTypeField = schemaManager.getFieldByName("food_type")
        expect(foodTypeField).toBeDefined();
    });

    it("tests getting fields by type", function(){
        var geopointFields = schemaManager.getFieldsByType(constants.GEOPOINT);
        expect(geopointFields.length).toEqual(1);
    });

    it("tests supported languages", function(){
        var supportedLanguages = schemaManager.getSupportedLanguages();
        expect(supportedLanguages.length).toEqual(1);
        expect(supportedLanguages[0]).toEqual("default");
    });

    it("tests field options", function(){
        expect(schemaManager.getFieldByName("food_type").options().length).toEqual(13);
    });
});

describe("Multi-lingual Schema manager tests", function(){
    var reader, loader, schemaManager;

    beforeEach(function() {
        var deferred;
        reader = new fh.Reader();
        loader = new fh.MemoryLoader(reader, datalibMock.multilang_schema);
        schemaManager = new fh.SchemaManager();

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

    it("tests supported languages", function(){
        var supportedLanguages = schemaManager.getSupportedLanguages();
        expect(supportedLanguages.length).toEqual(2);
        expect(supportedLanguages[0]).toEqual("French");
    });

    it("tests getting labels by language", function(){
        var locationPhotoField = schemaManager.getFieldByName("location_photo");
        expect(locationPhotoField.label()).toEqual("Served At Fr");
        // check that a label() called with a language returns the requested label
        expect(locationPhotoField.label("English")).toEqual("Served At");
    });

    it("tests that option labels are multilingual", function(){
        // TODO
    });
});

describe("DataManager tests", function(){
    var reader, dataLoader, schemaLoader, schemaManager, dataManager;

    beforeEach(function() {
        var deferred;
        reader = new fh.Reader();
        schemaLoader = new fh.MemoryLoader(reader, datalibMock.schema);
        schemaManager = new fh.SchemaManager();
        dataLoader = new fh.MemoryLoader(reader, datalibMock.data);
        dataManager = new fh.DataManager(schemaManager);

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
        var result = dataManager.dvQuery(query);
        expect(result[0][0]).toEqual(22);
    });

    it("tests the group by functionality", function(){
        var res = dataManager._dvTable.where(function(table, row){
            return table.get("food_type", row) === "lunch";
        });
        var result = dataManager.groupBy("food_type");
        var match = _.all(result, function(val, key){
            return datalibMock.dataByFoodType[key] === val;
        })
        expect(match).toBeTruthy();
    });
});
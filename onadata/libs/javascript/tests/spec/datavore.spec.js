describe("FH.DatavoreWrapper", function () {
    var fieldSet = new FH.FieldSet([
        {name: 'food_type', type: 'select one', label: 'Type of Food', xpath: 'good_eats/food_type', children: [
            {name: 'breakfast', label: 'Breakfast'}, {name: 'lunch', label: 'Lunch'}, {name: 'dinner', label: 'Dinner'}
        ]},
        {name: 'risk_factor', type: 'select one', label: 'How Risky', xpath: 'good_eats/risk_factor', children: [
            {name: 'high', label: 'High Risk'},
            {name: 'medium', label: 'Medium Risk'},
            {name: 'low', label: 'Low Risk'}
        ]},
        {name: 'rating', type: 'integer', label: 'Rate on a scale of 1 - 5', xpath: 'good_eats/rating'}
    ], {url: '/user/forms/test/form.json'});
    var dataSet = new FH.DataSet([
        {_id: 101, 'good_eats/food_type': 'breakfast', 'good_eats/risk_factor': 'high',   'good_eats/rating': 4},
        {_id: 107, 'good_eats/food_type': 'lunch',     'good_eats/risk_factor': 'low',    'good_eats/rating': 3},
        {_id: 108, 'good_eats/food_type': 'breakfast', 'good_eats/risk_factor': 'low',    'good_eats/rating': 5},
        {_id: 110, 'good_eats/food_type': 'dinner',    'good_eats/risk_factor': 'medium', 'good_eats/rating': 1},
        {_id: 111, 'good_eats/food_type': 'lunch',     'good_eats/risk_factor': 'low',    'good_eats/rating': 4},
        {_id: 112, 'good_eats/food_type': 'lunch',     'good_eats/risk_factor': 'high',   'good_eats/rating': 2},
        {_id: 115, 'good_eats/food_type': 'breakfast', 'good_eats/risk_factor': 'high',   'good_eats/rating': 2}
    ], {url: '/user/forms/test/form.json'});

    describe("FH.DatavoreWrapper.fhToDatavoreTypes", function () {
        it("returns nominal for select one", function () {
            var dvType = FH.DatavoreWrapper.fhToDatavoreType("select one");
            expect(dvType).toEqual(dv.type.nominal);
        });

        it("returns numeric for integers", function () {
            var dvType = FH.DatavoreWrapper.fhToDatavoreType("integer");
            expect(dvType).toEqual(dv.type.numeric);
        });

        it("returns numeric for decimal", function () {
            var dvType = FH.DatavoreWrapper.fhToDatavoreType("decimal");
            expect(dvType).toEqual(dv.type.numeric);
        });

        it("returns unknown for text", function () {
            var dvType = FH.DatavoreWrapper.fhToDatavoreType("text");
            expect(dvType).toEqual(dv.type.unknown);
        });

        it("returns unknown for geopoint", function () {
            var dvType = FH.DatavoreWrapper.fhToDatavoreType("geopoint");
            expect(dvType).toEqual(dv.type.unknown);
        });

        it("returns unknown for gps", function () {
            var dvType = FH.DatavoreWrapper.fhToDatavoreType("gps");
            expect(dvType).toEqual(dv.type.unknown);
        });
    });

    describe("DV Table initialisation", function () {
        var fhDatavore;

        beforeEach(function () {
            fhDatavore = new FH.DatavoreWrapper({'fieldSet': fieldSet, dataSet: dataSet});
        });

        it("initialises a datavore table on creation", function () {
            expect(fhDatavore.table).toBeDefined();
        });

        it("adds the meta _id field", function () {
            var idCol;

            idCol = fhDatavore.table.filter(function (col) {
                return col.name === '_id';
            })[0];
            expect(idCol).toBeDefined();
            expect(idCol.type).toEqual(dv.type.unknown);
        });

        it("sets up the correct number of rows and columns", function () {
            var cols;

            // 3 +  1 meta _id column
            expect(fhDatavore.table.cols()).toEqual(4);
            expect(fhDatavore.table.rows()).toEqual(7);

            cols = fhDatavore.table.map(function (c ){
                return c.name;
            });
            expect(cols).toContain('good_eats/food_type');
            expect(cols).toContain('good_eats/risk_factor');
            expect(cols).toContain('good_eats/rating');
        });

        it("properly sets the datavore columns types", function () {
            var targetCol;

            targetCol = fhDatavore.table.filter(function (col) {
                return col.name === 'good_eats/food_type';
            })[0];
            expect(targetCol.type).toEqual(dv.type.nominal);

            targetCol = fhDatavore.table.filter(function (col) {
                return col.name === 'good_eats/food_type';
            })[0];
            expect(targetCol.type).toEqual(dv.type.nominal);

            targetCol = fhDatavore.table.filter(function (col) {
                return col.name === 'good_eats/rating';
            })[0];
            expect(targetCol.type).toEqual(dv.type.numeric);
        });

        describe("API", function () {
            describe("countBy", function () {
                it("aggregates the data using the defined field and returns a mapping of field name's to count", function () {
                    var result = fhDatavore.countBy('good_eats/food_type'),
                        expectedResult = [
                            {key: 'breakfast', value: 3},
                            {key: 'lunch', value: 3},
                            {key: 'dinner', value: 1}
                        ];
                    expect(result).toContain(expectedResult[0]);
                    expect(result).toContain(expectedResult[1]);
                    expect(result).toContain(expectedResult[2]);
                });
            });
        });
    });
});

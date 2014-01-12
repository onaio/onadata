describe("FH.DataTableView", function () {
    describe("FH.DataTableView.NameOrLabel on select one", function () {
        var field = new FH.Field({
            _id: 'yes_no',
            xpath: 'group/yes_no',
            label: 'Yes or No',
            type: 'select one',
            children: [
                {
                    name: '0',
                    label: 'No'
                },
                {
                    name: '1',
                    label: 'Yes'
                }
            ]
        });

        it("should return the raw value when showLabels is disabled", function () {
            var result = FH.DataTableView.NameOrLabel(field, "0", false);
            expect(result).toEqual("0");

            result = FH.DataTableView.NameOrLabel(field, "1", false);
            expect(result).toEqual("1");
        });

        it("should return the select label when showLabels is enabled", function () {
            var result = FH.DataTableView.NameOrLabel(field, "0", true);
            expect(result).toEqual("No");

            result = FH.DataTableView.NameOrLabel(field, "1", true);
            expect(result).toEqual("Yes");
        });
    });

    describe("FH.DataTableView.NameOrLabel on select multiple", function () {
        var field = new FH.Field({
            _id: 'browsers',
            xpath: 'group/browsers',
            label: 'WHich browsers',
            type: 'select',
            children: [
                {
                    name: 'chrome',
                    label: 'Google Chrome'
                },
                {
                    name: 'firefox',
                    label: 'Mozilla Firefox'
                },
                {
                    name: 'ie',
                    label: 'Internet Explorer'
                }
            ]
        });

        it("should return a comma separated list of labels when showLabels is true", function(){
           var result = FH.DataTableView.NameOrLabel(field, "chrome ie", true).split(", ");
            expect(result).toContain("Google Chrome");
            expect(result).toContain("Internet Explorer");
        });
    });
});
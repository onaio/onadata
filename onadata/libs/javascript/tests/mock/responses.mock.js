var single_lang_form = {
        url: '/user/forms/single_lang/form.json',
        response: JSON.stringify({
            id_string: "tutorial",
            default_language: "default",
            type: "survey",
            name: "tutorial",
            sms_keyword: "tutorial",
            title: "Tutorial Form",
            children: [
                {
                    name: "start_time",
                    type: "start"
                },
                {
                    name: "end_time",
                    type: "end"
                },
                {
                    name: "instruction_note",
                    label: "Make sure you fill out the questionnaire accurately.",
                    type: "note"
                },
                {
                    name: "location",
                    hint: "So you can find it again",
                    label: "Location",
                    type: "gps"
                },
                {
                    name: "nearest_watering_hole",
                    hint: "Where is the nearest watering hole",
                    label: "Watering Hole",
                    type: "geopoint"
                },
                {
                    name: "a_group",
                    label: "A Group",
                    type: "group",
                    children: [
                        {
                            name: "how_epic",
                            label: "On a scale of 1-10, how epic an eat",
                            type: "integer"
                        },
                        {
                            name: "how_delectible",
                            label: "On a scale of 1-10, how delectible",
                            type: "integer"
                        },
                        {
                            name: "a_nested_group",
                            type: "group",
                            label: "A Nested Group",
                            children: [
                                {
                                    name: "nested_q",
                                    type: "text",
                                    label: "A Nested Q"
                                }
                            ]
                        }
                    ]
                },
                {
                    name: "rating",
                    label: "Rating",
                    type: "select one",
                    children: [
                        {
                            name: "nasty",
                            label: "Epic Eat"
                        },
                        {
                            name: "delectible",
                            label: "Delectible"
                        },
                        {
                            name: "nothing_special",
                            label: "Nothing Special"
                        },
                        {
                            name: "bad",
                            label: "What was I thinking"
                        }
                    ]
                }
            ]
        })
    };
var location_only_query = {
    url: '/user/forms/tutorial/api',
    response: JSON.stringify([
        {
            id: 1,
            location: "-1.262545 36.7924878 0.0 22.0"
        }
    ])
};
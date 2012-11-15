describe("Instance View tests", function() {
    it("checks that parseQuestions builds hierachies as expected", function() {
        expect(SurveyData.children).toBeDefined();
        expect(questions).toBeUndefined();
        questions = {};
        parseQuestions(SurveyData.children);
        // must only have one question since the rest are repeats/groups/notes
        expect(_.size(questions)).toEqual(1);
        expect(questions['note_one_a_group_a_question']).toBeDefined();
    });
});
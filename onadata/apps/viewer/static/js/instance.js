Question = function(questionData)
{
    this.name = questionData.name;
    this.type = questionData.type;
    this.label = questionData.label;
}

Question.prototype.getLabel = function(language)
{
    /// if plain string, return
    if(typeof(this.label) == "string")
        return this.label;
    else if(typeof(this.label) == "object")
    {
        if(language && this.label.hasOwnProperty(language))
            return this.label[language];
        else
        {
            var label = null;
            for(key in this.label)
            {
                label = this.label[key];
                break;// break at first instance and return that
            }
            return label;
        }

    }
    // return raw name
    return this.name;
}

function parseQuestions(children, prefix, cleanReplacement)
{
    var idx;
    cleanReplacement = typeof cleanReplacement !== 'undefined' ? cleanReplacement : '_';

    for(idx in children)
    {
        var question = children[idx];
        //@TODO: do we just want to add anything with children, concern could be it item has children and is alos avalid question - if thats possible
        if(question.hasOwnProperty('children') && (question.type == "group" || question.type == "note" || question.type == "repeat"))
        {
            parseQuestions(question.children, ((prefix?prefix:'') + question.name + cleanReplacement));
        }
        else
        {
            // TODO: question class that has accessor mesthods for type, label, language etc
            questions[((prefix?prefix:'') + question.name)] = new Question(question);
        }
    }
}

function addOrEditNote(){
        var instance_id = $("#instance_id").val(),
            note = $("#note").val().trim();
        if (note == ""){
            return false;
        }
        var notes_url = '/api/v1/notes',
            post_data = {'note': note, 'instance': instance_id};
        if($("#notesform #note-id").val() != undefined){
            // Edit Note
            post_data.pk = $("#notesform #note-id").val();
            notes_url += "/" + post_data.pk;
            $.ajax({
                url: notes_url,
                type: "PUT",
                data: post_data,
                statusCode: {
                    404: function(){
                        alert("Note \"" + note + "\" not found or already deleted.");
                        app.refresh();
                    }
                }
            }).done(function(data){
                $("#notesform")[0].reset();
                $("#notesform #note-id").remove();
                app.refresh();
            });
        } else {
            // Add New Note
            $.post(notes_url, post_data).done(function(data){
                $("#notesform")[0].reset();
                app.refresh();
            }).fail(function(data){console.log(data);})
        }
        return false;
    }


function parseLanguages(children)
{
    // run through question objects, stop at first question with label object and check it for multiple languages
    for(questionName in children)
    {
        var question = children[questionName];
        if(question.hasOwnProperty("label"))
        {
            var labelProp = question["label"];
            if(typeof(labelProp) == "string")
                languages = ["default"];
            else if(typeof(labelProp) == "object")
            {
                for(key in labelProp)
                {
                    languages.push(key)
                }
            }
            break;
        }
    }
    if (languages.length == 0) {
    	languages.push('en');
    }
}

function createTable(canEdit)
{
    var dataContainer = $('#data');
    dataContainer.empty();

    if(languages.length > 1)
    {
        var languageRow = $('<div class="row"></div>');
        var languageStr = $('<div class="span6"><span>' + gettext("Change Language:") + '</span> </div>');
        var languageSelect = $('<select class="language"></select>');
        var i;
        for(i = 0; i < languages.length; i++)
        {
            var language = languages[i];
            var languageOption = $('<option value="' + i +'">' + language + '</opton>');
            languageSelect.append(languageOption);
        }
        languageStr.append(languageSelect);
        languageRow.append(languageStr);
        dataContainer.append(languageRow);
    }

    // status and navigation rows - have to separate top and bottom since jquery doesnt append the same object twice
    var topStatusNavRows = $('<div class="row"></div>');
    var statusStr = '<div class="span6"><div class="dataTables_info"><h4 class="record-pos">' + gettext("Record 1 of 6") + '</h4></div></div>';
    var topStatus = $(statusStr);
    topStatusNavRows.append(topStatus);

    var pagerStr = '<div class="span6"><div class="dataTables_paginate paging_bootstrap pagination"><ul><li class="prev disabled"><a href="#">' + gettext("← Previous") + '</a></li><li class="next disabled"><a href="#">' + gettext("Next →") + '</a></li></ul></div></div>';
    var topPager = $(pagerStr);

    topStatusNavRows.append(topPager);
    dataContainer.append(topStatusNavRows);

    if(canEdit === true){
        var editDelete = '<div class="row"><div class="span6"><a id="title_edit" href="#kate" class="btn btn-small bind-edit disabled">' + gettext("edit") + '</a>&nbsp;<a href="#"class="btn btn-small btn-danger">' + gettext("Delete") + '</a></div></div>';
        dataContainer.append(editDelete);
    }
    var notesSection = '<div id="notes" style="display: none; margin: 10px"> \
    <form action="" onsubmit="return addOrEditNote()" method="post" name="notesform" id="notesform"> \
        <input type="hidden" value="" name="instance_id" id="instance_id" /> \
        <div class="controls"> \
        <textarea id="note" class="form-control" rows="2" name="note"\
        placeholder="'+ gettext("Add note to instance") + '" autocomplete="off" style="width: 80%"></textarea> \
        </div> \
        <div class="controls controls-row"> \
        <button type="submit" id="note_save" class="btn btn-small btn-primary" >' + gettext("Save note") + '</button> \
        </div>\
    </form> \
    <div id="notes-section"></div></div>';
    dataContainer.append(notesSection);

    var table = $('<table id="data-table" class="table table-bordered table-striped"></table');
    var tHead = $('<thead><tr><th class="header" width="50%">' + gettext("Question") + '</th><th class="header">' + gettext("Response") + '</th></tr></thead>');
    var tBody = $('<tbody></tbody>');
    var key;
    for(key in questions)
    {
        var question = questions[key];
        var tdLabel = $('<td></td>');
        var idx;
        for(idx in languages)
        {
            var language = languages[idx];
            var label = question.getLabel(language);
            var style = "display:none;";
            var spanLanguage = $('<span class="language language-' +idx +'" style="'+ style +'">'+ label +'</span>');
            tdLabel.append(spanLanguage);
        }
        var trData = $('<tr class=""></tr>');
        trData.append(tdLabel);
        var tdData = $('<td data-key="' + key + '"></td>');
        trData.append(tdData);
        tBody.append(trData);
    }
    table.append(tHead);
    table.append(tBody);
    dataContainer.append(table);

    var bottomStatusNavRows = $('<div class="row"></div>');
    var bottomStatus = $(statusStr);
    bottomStatusNavRows.append(bottomStatus);

    var bottomPager = $(pagerStr);

    bottomStatusNavRows.append(bottomPager);
    dataContainer.append(bottomStatusNavRows);

    $('select.language').change(function(){
        setLanguage(languages[parseInt($(this).val())]);
    });

    // set default language
    setLanguage(languages[0]);
}

function redirectToFirstId(context)
{
    $.getJSON(mongoAPIUrl, {'limit': 1, 'fields': '["_id"]', 'sort': '{"_id": 1}'})
            .success(function(data){
                if(data.length > 0)
                    context.redirect('#/' + data[0]['_id']);
            })
            .error(function(){
                app.run('#/');
            })
}

function deleteData(context, data_id, redirect_route){
    //TODO: show loader
    $.post(deleteAPIUrl, {'id': data_id})
            .success(function(data){
                // update data count
                $.getJSON(mongoAPIUrl, {'count': 1})
                        .success(function(data){
                            //todo: count num records before and num records after so we know our starting point
                            numRecords = data[0]["count"];
                            // redirect
                            context.redirect(redirect_route);
                        })
            })
            .error(function(){
               alert(gettext('BAD REQUEST'));
            })
}

function loadData(context, query, canEdit)
{

    //TODO: show loader
    $.getJSON(mongoAPIUrl, {'query': query, 'limit':1})
            .success(function(data){
                reDraw(context, data[0], canEdit);

                //ADD EDIT AND BUTTON CHECK PERMISSION
                updateButtons(data[0]);

                //alert(data[0]['_id']);
                // check if we initialised the browsePos
                if(false)//TODO: find a way to increment browsePos client-side
                {
                    updatePrevNextControls(data[0]);

                    // update pos status text
                    updatePosStatus();
                }
                else
                {
                    $.getJSON(mongoAPIUrl, {'query': '{"_id": {"$lt": ' + data[0]['_id'] +'}}', 'count': 1})
                            .success(function(posData){
                                browsePos = posData[0]["count"] + 1;
                                updatePrevNextControls(data[0]);
                            });
                }
            })
            .error(function(){
                alert(gettext("BAD REQUEST"));
            })
}

function setLanguage(language)
{
    var idx = languages.indexOf(language);
    if(idx>-1)
    {
        $('span.language').hide();
        $(('span.language-' + idx)).show();
    }
}

function updatePosStatus()
{
    var posText = positionTpl.replace('{pos}', browsePos);
    posText = posText.replace('{total}', numRecords);
    $('.record-pos').html(posText);
}

function updateButtons(data){

    //Make Edit Button visible and add link

    var editbutton = $('a.bind-edit');
    editbutton.removeClass('disabled');
    editbutton.attr('href', 'edit-data/' + data['_id']);


     //Make Delete Button visible and add link
    var deletebutton = $('a.btn-danger');
    deletebutton.removeClass('disabled');
    deletebutton.attr('href', '#del/' + data['_id']);
    $('a.btn-primary').attr('href', '#delete/' + data['_id']);

    // Add a note section
    $("#instance_id").val(data['_id']);
    $("#note").removeAttr("disabled");
}

function updatePrevNextControls(data)
{
    // load next record
    $.getJSON(mongoAPIUrl, {'query': '{"_id": {"$gt": ' + data['_id'] +'}}', 'limit': 1, 'sort': '{"_id":1}', 'fields':'["_id"]'})
            .success(function(nextData){
                var nextButton = $('li.next');
                if(nextData.length > 0)
                {
                    nextButton.removeClass('disabled');
                    nextButton.children('a').attr('href', '#/' + nextData[0]['_id']);
                }
                else
                {
                    nextButton.addClass('disabled');
                    // make next url "the" current url
                    nextButton.children('a').attr('href', '#/' + data['_id']);
                }
                // update pos status text
                updatePosStatus();
            });
    // load previous record
    $.getJSON(mongoAPIUrl, {'query': '{"_id": {"$lt": ' + data['_id'] +'}}', 'limit': 1, 'sort': '{"_id":-1}', 'fields':'["_id"]'})
            .success(function(prevData){
                var prevButton = $('li.prev');
                if(prevData.length > 0)
                {
                    prevButton.removeClass('disabled');
                    prevButton.children('a').attr('href', '#/' + prevData[0]['_id']);
                }
                else
                {
                    prevButton.addClass('disabled');
                    // make prev url "the" current url
                    prevButton.children('a').attr('href', '#/' + data['_id']);
                }
                // update pos status text
                updatePosStatus();

                // if we haven't checked our position before
                if(browsePos)
                {
                    // get num records before

                }
            });
}

function reDraw(context, data, canEdit)
{
    // make sure we have some data, if the id was in valid we would gte a blank array
    if(data)
    {
        var cleanData = {};
        var key;
        for(key in data)
        {
            var value = data[key];
            var cleanKey = key.replace(cleanRe, cleanReplacement);
            // check if its an image, audio or video and create thumbs or links to
            if(questions.hasOwnProperty(cleanKey))
            {
                if(questions[cleanKey].type == 'image' || questions[cleanKey].type == 'photo')
                {
                    var src = _attachment_url(value, 'small');
                    var href = _attachment_url(value, 'medium');
                    var imgTag = $('<img/>').attr('src', src);
                    value = $('<div>').append($('<a>').attr('href', href).attr('target', '_blank').append(imgTag)).html();
                }
                else if(questions[cleanKey].type == 'audio' || questions[cleanKey].type == 'video')
                {
                    var href = _attachment_url(value, 'medium');
                    value = $('<div>').append($('<a>').attr('href', href).attr('target', '_blank').append(value)).html();
                }
            }

            cleanData[cleanKey] = value;
        }

        // check if table has been created, if not reCreate
        if($('#data table').length == 0)
            createTable(canEdit);
        // clear data cells before we re-populate
        $('#data table td[data-key]').html('');
        context.meld($('#data'), cleanData, {
            selector: function(k) {
                k = k.replace(cleanRe, cleanReplacement);
                return '[data-key="' + k + '"]';
            }
        });

        $("#notes").show();

        var notes = data['_notes'], notesHTML = '<table class="table table-hover table-condensed">';
        if(notes.length > 0){
            for(note in notes){
                var n = notes[note];
                notesHTML += '<tr><td>' + n['note'] + '</td><td>' + n['date_modified'] + '</td><td>'
                    + '<button  onclick="editNote(this)" data-instance="' + n["instance"] + '" data-note="' + n['note'] + '" data-note-id="' + n['id'] + '" type="button" id="edit_note_' + n["id"] + '" class="btn btn-small btn-primary" >' + gettext("Edit note") + '</button>'
                    + '&nbsp;&nbsp;<i onclick="deleteNote(this)" data-instance="' + n["instance"] + '" data-note="' + n['note'] + '" data-note-id="' + n['id'] + '" class="remove-note icon-remove"></i>'
                    + '</td></tr>';
            }
            var nHTML = notesHTML + '</table>';
            $('#notes-section').html(nHTML);
        } else{
            $('#notes-section').empty();
        }

    }
    else
    {
        $('#data').empty();
        $('#data').html("<h3>" + gettext('The requested content was not found.') + "<h3>");
        $('#notes-section').empty();
        $("#notes").hide();
    }
}


function editNote(obj){
    var note = $(obj).data('note')
        , note_id = $(obj).data('note-id');
    $('<input>').attr({ type: 'hidden', id: 'note-id', name: 'id', value: note_id}).appendTo('#notesform');
    $("#notesform [name=note]").val(note);
}

function deleteNote(obj){
    var note = $(obj).data('note');
    var note_id = $(obj).data('note-id');
    if(confirm("Are you sure you want to delete \"" + note + "\"?") == true){
        $.ajax({
            url: "/api/v1/notes/" + note_id,
            type: "DELETE",
            statusCode: {
                404: function(){
                    alert("Note \"" + note + "\" not found or already deleted.");
                    app.refresh();
                }
            }
        }).done(function(data){
            app.refresh();
        });
    }
}

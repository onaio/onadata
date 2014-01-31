(function(){
    var root = this;

    root.ChartGridTemplate = _.template('<table class="table table-striped table-bordered table-condensed">' +
          '<thead>' +
            '<% if(show_header) { %>' +
            '<tr>' +
              '<th width="60%"><%= field_label %></th>' +
              '<th>count</th>' +
            '</tr>' +
            '<% } %>' +
          '</thead>' +
          '<tbody>' +
            '<% _.each(data, function(d) {%>' +
            '<tr>' +
              '<td width="60%"><%= d[field_label] %></td>' +
              '<td><%= d["count"] %></td>' +
            '</tr>' +
            '<% }) %>' +
          '</tbody>' +
        '</table>');
}).call(this);

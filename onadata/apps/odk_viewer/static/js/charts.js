(function(){
    var root = this;

    root.ChartGridTemplate = _.template('<table class="table table-striped">' +
          '<thead>' +
            '<tr>' +
              '<th><%= field_name %></th>' +
              '<th>Count</th>' +
            '</tr>' +
          '</thead>' +
          '<tbody>' +
            '<% _.each(data, function(d) {%>' +
            '<tr>' +
              '<td><%= d[field_name] %></td>' +
              '<td><%= d["count"] %></td>' +
            '</tr>' +
            '<% }) %>' +
          '</tbody>' +
        '</table>');
}).call(this);
(function(){
    var root = this;

    root.ChartGridTemplate = _.template('<table class="table table-striped table-bordered table-condensed stats-table">' +
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

    root.moreCharts = function (chart_url, page) {
        $('#more-charts').click(function () {
            var $self = $(this);
            if (!$self.hasClass('disabled')) {
                $self.addClass('disabled');
                $.get(chart_url + "?page=" + (++page), function (response) {
                    var html = $(response);
                    if (html.length > 0) {
                        $self.removeClass('disabled');
                        $('section#main').append(html);
                    } else {
                        $('#more-charts').remove();
                    }
                });
            }
        });
    }
}).call(this);

var root = (typeof exports !== "undefined" && exports !== null) ? exports : this;
this.fh = this.fh || {};
this.fh.template = this.fh.template || {};
(function(my){
    my.dataview = ' \
      <div class="fh-data-view"> \
        <div class="header clearfix"> \
          <div class="navigation"> \
            <div class="btn-group" data-toggle="buttons-radio"> \
              {{#views}} \
                <a href="#{{id}}" data-view="{{id}}" class="btn">{{label}}</a> \
              {{/views}} \
            </div>\
          </div> \
        </div> \
        <div class="data-view-sidebar"></div> \
        <div class="data-view-container"></div> \
      </div> \
    ';

    my.map = '\
    <div class="map"></map>\
    '
})(this.fh.template);
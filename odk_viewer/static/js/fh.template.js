this.fh = this.fh || {};
this.fh.template = this.fh.template || {};
(function(root){
    root.dataview = ' \
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

    root.map = '\
    <div class="map"></map>\
    '
})(this.fh.template);
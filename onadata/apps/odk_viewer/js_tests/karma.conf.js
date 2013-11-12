// Karma configuration
// Generated on Tue Oct 22 2013 15:54:54 GMT+0300 (EAT)

module.exports = function(config) {
  config.set({

    // base path, that will be used to resolve files and exclude
    basePath: '../../',


    // frameworks to use
    frameworks: ['jasmine'],


    // list of files / patterns to load in the browser
    files: [
      'main/static/bower_components/jquery/jquery.js',
      'main/static/bower_components/underscore/underscore.js',
      'main/static/bower_components/backbone/backbone.js',
      'main/static/bower_components/leaflet-dist/leaflet-src.js',
      'https://maps.google.com/maps/api/js?v=3.2&sensor=false',
      'main/static/js/dv.js',
      'main/static/js/Google.js',
      'node_modules/sinon/lib/sinon.js',
      'node_modules/sinon/lib/sinon/util/event.js',
      'node_modules/sinon/lib/sinon/util/fake_xml_http_request.js',
      'node_modules/sinon/lib/sinon/util/fake_server.js',
      'odk_viewer/static/js/map.js',
      'odk_viewer/static/js/xform.js',
      'odk_viewer/static/js/ajax_mock.js',
      'odk_viewer/js_tests/spec/*.js',
      'odk_viewer/js_tests/mock/*.js'
    ],


    // list of files to exclude
    exclude: [
      
    ],


    // test results reporter to use
    // possible values: 'dots', 'progress', 'junit', 'growl', 'coverage'
    reporters: ['progress'],


    // web server port
    port: 9876,


    // enable / disable colors in the output (reporters and logs)
    colors: true,


    // level of logging
    // possible values: config.LOG_DISABLE || config.LOG_ERROR || config.LOG_WARN || config.LOG_INFO || config.LOG_DEBUG
    logLevel: config.LOG_INFO,


    // enable / disable watching file and executing tests whenever any file changes
    autoWatch: false,


    // Start these browsers, currently available:
    // - Chrome
    // - ChromeCanary
    // - Firefox
    // - Opera
    // - Safari (only Mac)
    // - PhantomJS
    // - IE (only Windows)
    browsers: ['PhantomJS'],


    // If browser does not capture in given timeout [ms], kill it
    captureTimeout: 60000,


    // Continuous Integration mode
    // if true, it capture browsers, run tests and exit
    singleRun: true
  });
};

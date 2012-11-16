/*global module:false*/
module.exports = function(grunt) {

  // Project configuration.
  grunt.initConfig({
    meta: {
      version: '0.1.0',
      banner: '/*! formhub - v<%= meta.version %> - ' +
        '<%= grunt.template.today("yyyy-mm-dd") %>\n' +
        '* http://formhub.org/\n' +
        '* Copyright (c) <%= grunt.template.today("yyyy") %> ' +
        'modilabs; */'
    },
    lint: {
      files: ['grunt.js', 'odk_viewer/static/**/*.js']
    },
    test: {
      files: ['main/static/**/*.js', 'odk_logger/static/**/*.js', 'odk_viewer/static/**/*.js']
    },
    concat: {
      dist: {
        src: ['<banner:meta.banner>', '<file_strip_banner:lib/FILE_NAME.js>'],
        dest: 'dist/FILE_NAME.js'
      }
    },
    min: {
      dist: {
        src: ['<banner:meta.banner>', '<config:concat.dist.dest>'],
        dest: 'dist/FILE_NAME.min.js'
      }
    },
    watch: {
      files: ['<config:coffee.files>'],
      tasks: 'coffee:odk_viewer'
    },
    jshint: {
      options: {
        curly: true,
        eqeqeq: true,
        immed: true,
        latedef: true,
        newcap: true,
        noarg: true,
        sub: true,
        undef: true,
        boss: true,
        eqnull: true
      },
      globals: {
        jQuery: true
      }
    },
    uglify: {},
    less: {
        bootstrap: {
            files: {
                "main/static/bootstrap/css/bootstrap.css": "main/static/bootstrap/less/bootstrap-custom.less"
            }
        },
        responsive: {
            files: {
                "main/static/bootstrap/css/bootstrap-responsive.css": "main/static/bootstrap/less/responsive-custom.less"
            }
        },
        screen: {
            files: {
                "main/static/css/screen.css": "main/static/bootstrap/less/screen.less"
            }
        }
    },
    coffee: {
        files: ['odk_viewer/static/coffee/**/*.coffee'],
        main: {
            src: ['main/static/coffee/*.coffee'],
            dest: 'main/static/coffee/*.js'
        },
        odk_logger: {
            src: ['odk_logger/static/coffee/*.coffee'],
            dest: 'odk_logger/static/coffee/*.js'
        },
        odk_viewer: {
            src: ['odk_viewer/static/coffee/*.coffee'],
            dest: 'odk_viewer/static/js/',
            options: {
                bare: false // default false to create a closure for each file
            }
        }
    },
    jasmine:{
        src: ["main/static/js/underscore-min.js", "main/static/js/dv.js",
            "main/static/js/jquery-1.8.2.js", "odk_viewer/static/js/**/*.js",
            "main/static/js/fh_utils.js", "main/static/js/formManagers.js"],
        specs: ["js_tests/mocks/**/*.mock.js", "js_tests/specs/**/*.spec.js"]
    }
  });

  grunt.loadNpmTasks('grunt-contrib-less');
  grunt.loadNpmTasks('grunt-coffee');
  grunt.loadNpmTasks('grunt-jasmine-runner');

  // Default task.
  grunt.registerTask('default', 'coffee jasmine');

};

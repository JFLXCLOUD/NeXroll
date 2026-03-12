define([], function () {
    'use strict';

    var PLUGIN_ID = 'a1b2c3d4-e5f6-7890-abcd-ae0c01200002';

    function Controller(view, params) {
        this.view = view;

        var self = this;
        view.querySelector('#btnSave').addEventListener('click', function (e) {
            e.preventDefault();
            self.saveConfig();
        });
    }

    Controller.prototype.showResult = function (msg, color) {
        var el = this.view.querySelector('#saveResult');
        if (el) {
            el.style.color = color;
            el.textContent = msg;
        }
    };

    Controller.prototype.applyConfig = function (cfg) {
        var view = this.view;
        var el;
        el = view.querySelector('#chkMovies');
        if (el) el.checked = cfg.EnableForMovies !== false;
        el = view.querySelector('#chkEpisodes');
        if (el) el.checked = cfg.EnableForEpisodes !== false;
        el = view.querySelector('#txtMaxIntros');
        if (el) el.value = (typeof cfg.MaxIntros === 'number') ? cfg.MaxIntros : 0;

        var st = view.querySelector('#connectionStatus');
        if (!st) return;
        var url = cfg.NexrollUrl || '';
        if (url) {
            st.style.background = 'rgba(39,174,96,0.12)';
            st.style.border = '1px solid rgba(39,174,96,0.3)';
            st.innerHTML =
                '<span style="color:#27ae60;font-size:1.1em;font-weight:600;">&#10004; Connected to NeXroll</span>' +
                '<br/><span style="color:#999;font-size:0.9em;">Server: ' + url + '</span>';
        } else {
            st.style.background = 'rgba(231,76,60,0.12)';
            st.style.border = '1px solid rgba(231,76,60,0.3)';
            st.innerHTML =
                '<span style="color:#e74c3c;font-size:1.1em;font-weight:600;">&#10008; Not Connected</span>' +
                '<br/><span style="color:#999;font-size:0.9em;">Open your NeXroll dashboard and connect Emby.</span>';
        }
    };

    Controller.prototype.loadConfig = function () {
        var self = this;
        ApiClient.getPluginConfiguration(PLUGIN_ID).then(function (cfg) {
            self.applyConfig(cfg);
        });
    };

    Controller.prototype.saveConfig = function () {
        var self = this;
        var view = this.view;
        self.showResult('Saving...', '#999');

        ApiClient.getPluginConfiguration(PLUGIN_ID).then(function (cfg) {
            cfg.EnableForMovies = !!view.querySelector('#chkMovies').checked;
            cfg.EnableForEpisodes = !!view.querySelector('#chkEpisodes').checked;
            var raw = view.querySelector('#txtMaxIntros').value;
            var n = parseInt(raw, 10);
            cfg.MaxIntros = (isNaN(n) || n < 0) ? 0 : n;

            ApiClient.updatePluginConfiguration(PLUGIN_ID, cfg).then(function () {
                ApiClient.getPluginConfiguration(PLUGIN_ID).then(function (saved) {
                    self.applyConfig(saved);
                    self.showResult('\u2714 Saved \u2014 Max Intros: ' + saved.MaxIntros, '#27ae60');
                    try { Dashboard.processPluginConfigurationUpdateResult(); } catch (e) { }
                });
            }, function (err) {
                self.showResult('Save failed: ' + err, '#e74c3c');
            });
        }, function (err) {
            self.showResult('Load failed: ' + err, '#e74c3c');
        });
    };

    Controller.prototype.onResume = function (options) {
        this.loadConfig();
    };

    Controller.prototype.onPause = function () { };

    return Controller;
});

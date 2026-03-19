// ═══════════════════════════════════════════════════════════════════════════
// Helix — Stream Deck Plugin  (SDK v2)
//
// Polls GET /api/streamdeck every second and renders SVG key images that
// reflect live state.  Pressing a key sends the matching POST toggle/cycle
// request, then immediately re-polls so the icon updates without waiting
// for the next tick.
// ═══════════════════════════════════════════════════════════════════════════

var websocket    = null;
var pluginUUID   = null;
var globalSettings = {};          // { serverUrl: "http://…:8000" }
var contexts     = {};            // context → { action, settings }
var pollTimer    = null;
var lastState    = null;

// ── Entry point (called by Stream Deck software) ────────────────────────

function connectElgatoStreamDeckSocket(port, uuid, registerEvent, info) {
    pluginUUID = uuid;

    websocket = new WebSocket('ws://127.0.0.1:' + port);

    websocket.onopen = function () {
        websocket.send(JSON.stringify({ event: registerEvent, uuid: uuid }));
        websocket.send(JSON.stringify({ event: 'getGlobalSettings', context: uuid }));
    };

    websocket.onmessage = function (evt) {
        var msg = JSON.parse(evt.data);
        switch (msg.event) {
            case 'keyDown':                  onKeyDown(msg);               break;
            case 'willAppear':               onWillAppear(msg);            break;
            case 'willDisappear':            onWillDisappear(msg);         break;
            case 'didReceiveSettings':       onDidReceiveSettings(msg);    break;
            case 'didReceiveGlobalSettings': onDidReceiveGlobalSettings(msg); break;
            case 'sendToPlugin':             onSendToPlugin(msg);           break;
        }
    };

    websocket.onclose = function () {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    };
}

// ── Event handlers ──────────────────────────────────────────────────────

function onKeyDown(msg) {
    var action   = msg.action;
    var ctx      = msg.context;
    var settings = (msg.payload && msg.payload.settings) || {};
    var url      = settings.serverUrl || globalSettings.serverUrl || '';

    var endpoint = null;
    if (action === 'com.helix.recoil')     endpoint = '/api/recoil/toggle';
    if (action === 'com.helix.flashlight') endpoint = '/api/flashlight/toggle';
    if (action === 'com.helix.cycle')      endpoint = '/api/scripts/cycle';

    if (endpoint && url) {
        fetch(url + endpoint, { method: 'POST' })
            .then(function () { pollState(); })
            .catch(function () { showAlert(ctx); });
    }
}

function onWillAppear(msg) {
    contexts[msg.context] = {
        action:   msg.action,
        settings: (msg.payload && msg.payload.settings) || {}
    };

    sendSD('setTitle', msg.context, { title: '', target: 0 });
    setIconForContext(msg.context, msg.action, null);

    if (!pollTimer) {
        pollState();
        pollTimer = setInterval(pollState, 1000);
    }
}

function onWillDisappear(msg) {
    delete contexts[msg.context];
    if (Object.keys(contexts).length === 0 && pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

function onDidReceiveSettings(msg) {
    if (contexts[msg.context]) {
        contexts[msg.context].settings = msg.payload.settings || {};
    }
    pollState();
}

function onDidReceiveGlobalSettings(msg) {
    globalSettings = msg.payload.settings || {};
    pollState();
}

function onSendToPlugin(msg) {
    var payload = msg.payload || {};
    if (payload.command === 'testConnection') {
        var url = payload.url || '';
        fetch(url + '/api/health?_t=' + Date.now())
            .then(function (r) { return r.json(); })
            .then(function (d) {
                sendSD('sendToPropertyInspector', msg.context, {
                    command: 'testResult', success: true, makcu: d.makcu
                });
            })
            .catch(function () {
                sendSD('sendToPropertyInspector', msg.context, {
                    command: 'testResult', success: false
                });
            });
    }
}

// ── State polling ───────────────────────────────────────────────────────

function pollState() {
    if (Object.keys(contexts).length === 0) return;

    var byUrl = {};
    Object.keys(contexts).forEach(function (ctx) {
        var url = contexts[ctx].settings.serverUrl || globalSettings.serverUrl || '';
        if (!url) return;
        if (!byUrl[url]) byUrl[url] = [];
        byUrl[url].push(ctx);
    });

    Object.keys(byUrl).forEach(function (url) {
        fetch(url + '/api/streamdeck?_t=' + Date.now())
            .then(function (r) { return r.json(); })
            .then(function (state) {
                lastState = state;
                byUrl[url].forEach(function (ctx) {
                    if (contexts[ctx]) {
                        setIconForContext(ctx, contexts[ctx].action, state);
                    }
                });
            })
            .catch(function () {
                byUrl[url].forEach(function (ctx) {
                    if (contexts[ctx]) {
                        setIconForContext(ctx, contexts[ctx].action, { _error: true });
                    }
                });
            });
    });
}

// ── Icon rendering + setImage ───────────────────────────────────────────

function setIconForContext(ctx, action, state) {
    var svg = null;
    var err = !state || state._error;

    if (action === 'com.helix.recoil') {
        svg = renderRecoilIcon(err ? false : state.recoil, err);
    } else if (action === 'com.helix.flashlight') {
        svg = renderFlashlightIcon(err ? false : state.flashlight, err);
    } else if (action === 'com.helix.cycle') {
        svg = renderCycleIcon(err ? null : state.script, err);
    } else if (action === 'com.helix.status') {
        svg = renderStatusIcon(err ? false : state.makcu, err);
    }

    if (svg) {
        var b64 = btoa(unescape(encodeURIComponent(svg)));
        sendSD('setImage', ctx, {
            image:  'data:image/svg+xml;base64,' + b64,
            target: 0
        });
    }
}

// ── SVG renderers ───────────────────────────────────────────────────────

function renderRecoilIcon(on, error) {
    var c  = error ? '#ff4444' : (on ? '#44ff77' : '#ff4444');
    var bc = error ? '#2a1818' : (on ? '#1a3a20' : '#2a1818');
    var op = error ? 0.3 : (on ? 1 : 0.45);
    var lb = error ? '\u2014' : (on ? 'ON' : 'OFF');

    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 144 144" width="144" height="144">'
        + '<defs><filter id="g"><feGaussianBlur stdDeviation="3.5" result="b"/>'
        + '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
        + '<rect width="144" height="144" rx="18" fill="#0f1012" stroke="' + bc + '" stroke-width="1.5"/>'
        + (on ? '<rect x="16" y="137" width="112" height="4" rx="2" fill="' + c + '" opacity="0.35"/>' : '')
        + '<g transform="translate(72,42)" opacity="' + op + '"' + (on ? ' filter="url(#g)"' : '') + '>'
        + (on ? '<circle r="26" fill="none" stroke="' + c + '" stroke-width="1.5" opacity="0.15"/>' : '')
        + '<circle r="14" fill="none" stroke="' + c + '" stroke-width="2.5"/>'
        + '<line x1="0" y1="-28" x2="0" y2="-18" stroke="' + c + '" stroke-width="2.5" stroke-linecap="round"/>'
        + '<line x1="0" y1="18" x2="0" y2="28" stroke="' + c + '" stroke-width="2.5" stroke-linecap="round"/>'
        + '<line x1="-28" y1="0" x2="-18" y2="0" stroke="' + c + '" stroke-width="2.5" stroke-linecap="round"/>'
        + '<line x1="18" y1="0" x2="28" y2="0" stroke="' + c + '" stroke-width="2.5" stroke-linecap="round"/>'
        + '<circle r="3" fill="' + c + '"/>'
        + (!on && !error ? '<line x1="-10" y1="-10" x2="10" y2="10" stroke="' + c + '" stroke-width="2.5" stroke-linecap="round" opacity="0.8"/>' : '')
        + '</g>'
        + '<text x="72" y="100" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="19" fill="' + c + '" letter-spacing="2" opacity="' + (on ? 1 : 0.55) + '">RECOIL</text>'
        + '<text x="72" y="128" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="24" fill="' + c + '" opacity="' + (on ? 0.9 : 0.5) + '">' + lb + '</text>'
        + '</svg>';
}

function renderFlashlightIcon(on, error) {
    var c  = error ? '#ff4444' : (on ? '#ffbb33' : '#ff4444');
    var bc = error ? '#2a1818' : (on ? '#2a2a15' : '#2a1818');
    var op = error ? 0.3 : (on ? 1 : 0.4);
    var lb = error ? '\u2014' : (on ? 'ON' : 'OFF');

    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 144 144" width="144" height="144">'
        + '<defs><filter id="g"><feGaussianBlur stdDeviation="3.5" result="b"/>'
        + '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
        + '<rect width="144" height="144" rx="18" fill="#0f1012" stroke="' + bc + '" stroke-width="1.5"/>'
        + (on ? '<rect x="16" y="137" width="112" height="4" rx="2" fill="' + c + '" opacity="0.35"/>' : '')
        + '<g transform="translate(72,40)" opacity="' + op + '"' + (on ? ' filter="url(#g)"' : '') + '>'
        + (on ? '<ellipse rx="20" ry="26" fill="' + c + '" opacity="0.06"/>' : '')
        + '<polygon points="2,-26 -10,0 -1,0 -6,26 12,0 3,0" fill="' + c + '" stroke="' + c + '" stroke-width="0.5" stroke-linejoin="round"/>'
        + '</g>'
        + '<text x="72" y="100" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="19" fill="' + c + '" letter-spacing="2" opacity="' + (on ? 1 : 0.55) + '">FLASH</text>'
        + '<text x="72" y="128" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="24" fill="' + c + '" opacity="' + (on ? 0.9 : 0.5) + '">' + lb + '</text>'
        + '</svg>';
}

function renderCycleIcon(scriptName, error) {
    var c  = error ? '#ff4444' : '#4d9cff';
    var bc = error ? '#2a1818' : '#152a3a';
    var op = error ? 0.3 : 1;

    var name = scriptName || 'NONE';
    // Strip game prefix: "ABI/MDR" → "MDR"
    var slash = name.lastIndexOf('/');
    if (slash >= 0) name = name.substring(slash + 1);

    // Dynamic font size — shrink to fit long names (120px max width)
    var fs;
    if      (name.length <= 4)  fs = 32;
    else if (name.length <= 6)  fs = 26;
    else if (name.length <= 8)  fs = 22;
    else if (name.length <= 10) fs = 18;
    else if (name.length <= 14) fs = 14;
    else                        fs = 11;

    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 144 144" width="144" height="144">'
        + '<rect width="144" height="144" rx="18" fill="#0f1012" stroke="' + bc + '" stroke-width="1.5"/>'
        + '<g transform="translate(72,30)" opacity="' + op + '">'
        + '<path d="M0,-14 A14,14 0 0 1 12,7" fill="none" stroke="' + c + '" stroke-width="2.5" stroke-linecap="round"/>'
        + '<path d="M0,14 A14,14 0 0 1 -12,-7" fill="none" stroke="' + c + '" stroke-width="2.5" stroke-linecap="round"/>'
        + '<polygon points="10,3 16,10 8,10" fill="' + c + '"/>'
        + '<polygon points="-10,-3 -16,-10 -8,-10" fill="' + c + '"/>'
        + '</g>'
        + '<text x="72" y="78" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="13" fill="' + c + '" letter-spacing="2" opacity="' + (error ? 0.4 : 0.6) + '">CYCLE</text>'
        + '<text x="72" y="116" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="' + fs + '" fill="' + c + '" opacity="' + (error ? 0.5 : 1) + '">' + escXml(name) + '</text>'
        + '</svg>';
}

function renderStatusIcon(connected, error) {
    var c  = error ? '#ff4444' : (connected ? '#44ff77' : '#ff4444');
    var bc = error ? '#2a1818' : (connected ? '#1a3a20' : '#2a1818');
    var op = error ? 0.3 : (connected ? 1 : 0.5);
    var lb = error ? '\u2014' : (connected ? 'OK' : 'ERR');

    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 144 144" width="144" height="144">'
        + '<defs><filter id="g"><feGaussianBlur stdDeviation="3.5" result="b"/>'
        + '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
        + '<rect width="144" height="144" rx="18" fill="#0f1012" stroke="' + bc + '" stroke-width="1.5"/>'
        + (connected ? '<rect x="16" y="137" width="112" height="4" rx="2" fill="' + c + '" opacity="0.35"/>' : '')
        + '<g transform="translate(72,40)" opacity="' + op + '"' + (connected ? ' filter="url(#g)"' : '') + '>'
        + '<rect x="-16" y="-14" width="32" height="28" rx="4" fill="none" stroke="' + c + '" stroke-width="2.5"/>'
        + '<rect x="-8" y="-24" width="16" height="14" rx="2" fill="none" stroke="' + c + '" stroke-width="2"/>'
        + '<line x1="-4" y1="-24" x2="-4" y2="-14" stroke="' + c + '" stroke-width="1.5"/>'
        + '<line x1="4" y1="-24" x2="4" y2="-14" stroke="' + c + '" stroke-width="1.5"/>'
        + '<circle cy="2" r="4" fill="' + c + '" opacity="0.9"/>'
        + '</g>'
        + (!connected && !error
            ? '<g transform="translate(72,40)" opacity="0.6">'
              + '<line x1="-8" y1="-8" x2="8" y2="8" stroke="' + c + '" stroke-width="2.5" stroke-linecap="round"/>'
              + '<line x1="8" y1="-8" x2="-8" y2="8" stroke="' + c + '" stroke-width="2.5" stroke-linecap="round"/></g>'
            : '')
        + '<text x="72" y="100" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="19" fill="' + c + '" letter-spacing="2" opacity="' + (connected ? 1 : 0.55) + '">MAKCU</text>'
        + '<text x="72" y="128" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="24" fill="' + c + '" opacity="' + (connected ? 0.9 : 0.5) + '">' + lb + '</text>'
        + '</svg>';
}

// ── Helpers ─────────────────────────────────────────────────────────────

function sendSD(event, context, payload) {
    if (websocket && websocket.readyState === 1) {
        websocket.send(JSON.stringify({ event: event, context: context, payload: payload }));
    }
}

function showAlert(ctx) { sendSD('showAlert', ctx, {}); }

function escXml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&apos;');
}

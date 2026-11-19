// (function () {
//   'use strict';

//   var DEBUG = true; // set to false once everything works
//   function log() {
//     if (DEBUG) console.log.apply(console, ['[PWA]'].concat([].slice.call(arguments)));
//   }

//   // 1. Register the service worker
//   if ('serviceWorker' in navigator) {
//     window.addEventListener('load', function () {
//       navigator.serviceWorker.register('/sw.js', { scope: '/' })
//         .then(function () { log('service worker registered'); })
//         .catch(function (err) { console.error('[PWA] service worker failed:', err); });
//     });
//   }

//   // 2. Install card
//   var DISMISS_KEY = 'kwik_install_dismissed_at';
//   var SNOOZE_DAYS = 0.01;
//   var SHOW_DELAY_MS = 2500;

//   if (location.search.indexOf('pwa=reset') !== -1) {
//   try { localStorage.removeItem('kwik_install_dismissed_at'); } catch (e) {}
//   log('snooze cleared');
// }

//   var card = document.getElementById('kwik-pwa-card');
//   if (!card) { log('install card not found in page'); return; }

//   var textEl = document.getElementById('kwik-pwa-text');
//   var installBtn = document.getElementById('kwik-pwa-install');
//   var laterBtn = document.getElementById('kwik-pwa-later');

//   var isStandalone =
//     window.matchMedia('(display-mode: standalone)').matches ||
//     window.navigator.standalone === true;

//   var isIos = /iphone|ipad|ipod/i.test(navigator.userAgent) ||
//     (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

//   function snoozed() {
//     try {
//       var t = parseInt(localStorage.getItem(DISMISS_KEY) || '0', 10);
//       return t && (Date.now() - t) < SNOOZE_DAYS * 86400000;
//     } catch (e) { return false; }
//   }
//   function show() { card.classList.add('is-visible'); }
//   function hide() { card.classList.remove('is-visible'); }
//   function snooze() {
//     try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch (e) {}
//     hide();
//   }

//   if (isStandalone) { log('already running as an installed app'); return; }
//   if (snoozed()) { log('card snoozed (dismissed within the last ' + SNOOZE_DAYS + ' days)'); return; }

//   var timer = null;
//   function showSoon() {
//     clearTimeout(timer);
//     timer = setTimeout(show, SHOW_DELAY_MS);
//   }

//   if (isIos) {
//     // iOS has no install API, so show manual instructions
//     textEl.innerHTML = 'Tap <b>Share</b>, then <b>Add to Home Screen</b>.';
//     installBtn.style.display = 'none';
//     laterBtn.textContent = 'Got it';
//     showSoon();
//   } else {
//     if (window.__pwaPrompt) { log('install event was already captured'); showSoon(); }
//     window.addEventListener('pwa-installable', function () {
//       log('install event received');
//       showSoon();
//     });
//   }

//   installBtn.addEventListener('click', function () {
//     var p = window.__pwaPrompt;
//     if (!p) return;
//     p.prompt();
//     p.userChoice.then(function (choice) {
//       log('user choice:', choice.outcome);
//       window.__pwaPrompt = null;
//       if (choice.outcome === 'dismissed') { snooze(); } else { hide(); }
//     });
//   });

//   laterBtn.addEventListener('click', snooze);
//   window.addEventListener('appinstalled', function () { log('app installed'); hide(); });
// })();

(function () {
  'use strict';

  // Set to true while testing to see "[PWA]" messages in the browser console.
  var DEBUG = false;
  function log() {
    if (DEBUG) console.log.apply(console, ['[PWA]'].concat([].slice.call(arguments)));
  }

  // ---------------------------------------------------------------
  // 1. Register the service worker
  // ---------------------------------------------------------------
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then(function () { log('service worker registered'); })
        .catch(function (err) { console.error('[PWA] service worker failed:', err); });
    });
  }

  // ---------------------------------------------------------------
  // 2. Install card
  // ---------------------------------------------------------------
  var DISMISS_KEY = 'kwik_install_dismissed_at';
  var DISMISS_COUNT_KEY = 'kwik_install_dismiss_count';
  var SHOW_DELAY_MS = 2500;

  // Testing shortcut: visit /?pwa=reset to clear all snooze data
  if (location.search.indexOf('pwa=reset') !== -1) {
    try {
      localStorage.removeItem(DISMISS_KEY);
      localStorage.removeItem(DISMISS_COUNT_KEY);
    } catch (e) {}
    log('snooze cleared');
  }

  var card = document.getElementById('kwik-pwa-card');
  if (!card) { log('install card not found in page'); return; }

  var textEl = document.getElementById('kwik-pwa-text');
  var installBtn = document.getElementById('kwik-pwa-install');
  var laterBtn = document.getElementById('kwik-pwa-later');

  var isStandalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;

  var isIos = /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

  // Escalating snooze: 7 days, then 30 days, then 90 days
  function snoozeDays() {
    var count = 0;
    try { count = parseInt(localStorage.getItem(DISMISS_COUNT_KEY) || '0', 10); } catch (e) {}
    if (count <= 1) return 7;
    if (count === 2) return 30;
    return 90;
  }

  function snoozed() {
    try {
      var t = parseInt(localStorage.getItem(DISMISS_KEY) || '0', 10);
      return t && (Date.now() - t) < snoozeDays() * 86400000;
    } catch (e) { return false; }
  }

  function show() { card.classList.add('is-visible'); }
  function hide() { card.classList.remove('is-visible'); }

  function snooze() {
    try {
      var count = parseInt(localStorage.getItem(DISMISS_COUNT_KEY) || '0', 10);
      localStorage.setItem(DISMISS_COUNT_KEY, String(count + 1));
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch (e) {}
    hide();
  }

  if (isStandalone) { log('already running as an installed app'); return; }
  if (snoozed()) { log('card snoozed for ' + snoozeDays() + ' days'); return; }

  var timer = null;
  function showSoon() {
    clearTimeout(timer);
    timer = setTimeout(show, SHOW_DELAY_MS);
  }

  if (isIos) {
    // iOS has no install API, so show manual instructions
    textEl.innerHTML = 'Tap <b>Share</b>, then <b>Add to Home Screen</b>.';
    installBtn.style.display = 'none';
    laterBtn.textContent = 'Got it';
    showSoon();
  } else {
    // The install event is captured early in <head> (pwa_head.html)
    if (window.__pwaPrompt) { log('install event was already captured'); showSoon(); }
    window.addEventListener('pwa-installable', function () {
      log('install event received');
      showSoon();
    });
  }

  installBtn.addEventListener('click', function () {
    var p = window.__pwaPrompt;
    if (!p) return;
    p.prompt();
    p.userChoice.then(function (choice) {
      log('user choice:', choice.outcome);
      window.__pwaPrompt = null;
      if (choice.outcome === 'dismissed') { snooze(); } else { hide(); }
    });
  });

  laterBtn.addEventListener('click', snooze);
  window.addEventListener('appinstalled', function () { log('app installed'); hide(); });
})();

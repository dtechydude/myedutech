(function () {
  "use strict";

  var wrappers = Array.prototype.slice.call(document.querySelectorAll("[data-youtube-id]"));
  if (!wrappers.length) return;

  // Swap the player for the friendly message + "Watch on YouTube" button.
  function showFallback(wrapper) {
    var frame = wrapper.querySelector(".kws-video__frame");
    var notice = wrapper.querySelector(".kws-video__fallback");
    var link = wrapper.querySelector(".kws-video__link");
    if (frame) frame.hidden = true;
    if (link) link.hidden = true;
    if (notice) notice.hidden = false;
  }

  function createPlayer(wrapper) {
    var mount = wrapper.querySelector(".kws-video__player");
    if (!mount) return;

    // If the player never becomes ready (blocked network, etc.), fall back.
    var timer = setTimeout(function () { showFallback(wrapper); }, 12000);

    new YT.Player(mount, {
      host: "https://www.youtube-nocookie.com",
      videoId: wrapper.getAttribute("data-youtube-id"),
      width: "100%",
      height: "100%",
      playerVars: {
        rel: 0,
        modestbranding: 1,
        playsinline: 1,
        origin: window.location.origin   // identifies your site to YouTube (prevents 153)
      },
      events: {
        onReady: function () { clearTimeout(timer); },
        onError: function () { clearTimeout(timer); showFallback(wrapper); }
      }
    });
  }

  function initAll() { wrappers.forEach(createPlayer); }

  if (window.YT && window.YT.Player) {
    initAll();
    return;
  }

  var previous = window.onYouTubeIframeAPIReady;
  window.onYouTubeIframeAPIReady = function () {
    if (typeof previous === "function") previous();
    initAll();
  };

  var tag = document.createElement("script");
  tag.src = "https://www.youtube.com/iframe_api";
  tag.async = true;
  tag.onerror = function () { wrappers.forEach(showFallback); };  // e.g. YouTube blocked on the school network
  document.head.appendChild(tag);
})();
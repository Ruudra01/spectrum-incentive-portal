/* Foundation interaction layer. No libraries. Everything hangs off window.SP. */
(function (window, document) {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Counts up to an integer with an ease-out curve. */
  function animateCount(el, target, duration) {
    target = Number(target);
    duration = duration || 1400;
    if (reduced) {
      el.textContent = target.toLocaleString();
      return;
    }
    var start = null;
    (function step(now) {
      if (start === null) start = now;
      var p = Math.min((now - start) / duration, 1);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))).toLocaleString();
      if (p < 1) requestAnimationFrame(step);
    })(performance.now());
  }

  /* Reveals .u-reveal elements on entry, staggered by their order on screen. */
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry, i) {
      if (!entry.isIntersecting) return;
      var el = entry.target;
      observer.unobserve(el);
      el.style.transitionDelay = reduced ? "0ms" : i * 60 + "ms";
      el.classList.add("is-visible");
      if (el.dataset.count) animateCount(el, el.dataset.count, el.dataset.countDuration);
    });
  }, { threshold: 0.2, rootMargin: "0px 0px -40px 0px" });

  /* Dismissible bottom-left notice. */
  function toast(message) {
    var host = document.querySelector(".sp-toasts");
    if (!host) {
      host = document.createElement("div");
      host.className = "sp-toasts";
      document.body.appendChild(host);
    }
    var node = document.createElement("div");
    node.className = "sp-toast";
    node.setAttribute("role", "status");
    node.innerHTML = '<span class="sp-toast-text"></span>' +
      '<button type="button" class="sp-toast-close" aria-label="Dismiss">&times;</button>';
    node.querySelector(".sp-toast-text").textContent = message;
    node.querySelector(".sp-toast-close").addEventListener("click", function () {
      node.remove();
    });
    host.appendChild(node);
    requestAnimationFrame(function () { node.classList.add("is-visible"); });
    return node;
  }

  function init() {
    document.querySelectorAll(".u-reveal").forEach(function (el) { observer.observe(el); });
  }

  window.SP = { animateCount: animateCount, toast: toast, observe: observer.observe.bind(observer) };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window, document);

/* Foundation interaction layer. No libraries. Everything hangs off window.SP. */
(function (window, document) {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Counts up to a number with an ease-out curve. Decimal places come from
     data-count-decimals so rates and scores do not round to integers. */
  function animateCount(el, target, duration, decimals) {
    target = Number(target);
    duration = duration || 1400;
    decimals = decimals === undefined ? parseInt(el.dataset.countDecimals || "0", 10) : decimals;
    var format = { minimumFractionDigits: decimals, maximumFractionDigits: decimals };
    if (reduced) {
      el.textContent = target.toLocaleString(undefined, format);
      return;
    }
    var start = null;
    (function step(now) {
      if (start === null) start = now;
      var p = Math.min((now - start) / duration, 1);
      el.textContent = (target * (1 - Math.pow(1 - p, 3))).toLocaleString(undefined, format);
      if (p < 1) requestAnimationFrame(step);
    })(performance.now());
  }

  /* Reveals .u-reveal elements on entry, staggered by their order on screen,
     and counts up anything carrying data-count. The two are observed together
     but are independent: a count-up does not need to be a reveal, which is why
     init() below watches both selectors. */
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
    /* [data-count] is observed in its own right. Requiring .u-reveal as well
       left every KPI figure outside the landing page showing its literal "0"
       fallback, because only that one element happened to carry both. */
    document.querySelectorAll(".u-reveal, [data-count]").forEach(function (el) {
      observer.observe(el);
    });
  }

  window.SP = {
    animateCount: animateCount,
    toast: toast,
    observe: observer.observe.bind(observer),
    reducedMotion: reduced
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window, document);

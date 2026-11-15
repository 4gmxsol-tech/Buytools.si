(function () {
  "use strict";
  var CONSENT_KEY = "buytools-ad-consent-v1";
  var NATIVE_ID = "8da1edf07cede895489f2b1512afb817";
  var units = {
    mobile: "7d2bbc2740564e43a9e7f0dfc203a048",
    tablet: "823b02f7bebf1515b0c35c679b3fb8de",
    desktop: "f3a9600bd82256bc27531864fa84038f"
  };
  var nativePages = location.pathname === "/" || location.pathname.indexOf("/guides/") === 0;
  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    if (text) node.textContent = text;
    return node;
  }
  var consentReadFailed = false;
  var preferencesButton = null;
  function readConsent() {
    try { return window.localStorage.getItem(CONSENT_KEY); }
    catch (error) { consentReadFailed = true; return null; }
  }
  function saveConsent(value) {
    try { window.localStorage.setItem(CONSENT_KEY, value); return true; }
    catch (error) { return false; }
  }
  function closeConsentPanel() {
    var panel = document.getElementById("buytools-ad-consent");
    if (panel) panel.remove();
    if (preferencesButton) preferencesButton.setAttribute("aria-expanded", "false");
  }
  function handleConsentStorage(event) {
    if (!event || (event.key !== CONSENT_KEY && event.key !== null)) return;
    try {
      if (event.storageArea && event.storageArea !== window.localStorage) return;
    } catch (error) {
      return;
    }
    var nextValue = event.key === null ? null : event.newValue;
    var notice = document.getElementById("buytools-ad-consent-notice");
    if (notice) notice.remove();
    if (nextValue === "accepted") {
      closeConsentPanel();
      mountAds();
      return;
    }
    var existingSlot = document.getElementById("buytools-ad-slot");
    var hadAdSlot = !!existingSlot;
    if (existingSlot) existingSlot.remove();
    closeConsentPanel();
    if (hadAdSlot) {
      window.location.reload();
      return;
    }
    if (nextValue !== "rejected") showConsent(false);
  }
  function showConsentNotice(adWasAlreadyRequested) {
    if (document.getElementById("buytools-ad-consent-notice")) return;
    var message = adWasAlreadyRequested
      ? "Your rejection applies to this page, but your browser could not save the preference. The ad slot has been removed; third-party code already requested during this page cannot be recalled. A previously saved preference, if any, may still apply after navigation or reload."
      : "Your rejection applies to this page, but your browser could not confirm that it saved the preference. A previously saved preference, if any, may still apply after navigation or reload.";
    var notice = el("p", {
      id: "buytools-ad-consent-notice",
      role: "status",
      "aria-live": "polite",
      class: "buytools-ad-consent-notice"
    }, message);
    var main = document.querySelector("main");
    if (main) main.insertBefore(notice, main.firstChild);
    else document.body.insertBefore(notice, document.body.firstChild);
  }
  function loadNative(target) {
    var script = el("script", { async: "async", "data-cfasync": "false", src: "https://bicea.org/21/" + NATIVE_ID });
    target.appendChild(script);
    target.appendChild(el("div", { id: "container-" + NATIVE_ID }));
  }
  function loadBanner(target) {
    var width = window.innerWidth;
    var size = width < 520 ? [320, 50, units.mobile] : width < 900 ? [300, 250, units.tablet] : [728, 90, units.desktop];
    var w = size[0], h = size[1], key = size[2];
    target.style.minHeight = h + "px";
    target.style.maxWidth = w + "px";
    target.style.margin = "0 auto";
    var options = el("script", {});
    options.text = "atOptions = { 'key': '" + key + "', 'format': 'iframe', 'height': " + h + ", 'width': " + w + ", 'params': {} };";
    target.appendChild(options);
    target.appendChild(el("script", { src: "https://bicea.org/22/" + key, async: "async" }));
  }
  function mountAds() {
    if (document.getElementById("buytools-ad-slot")) return;
    var slot = el("section", { id: "buytools-ad-slot", "aria-label": "Advertisement", class: "buytools-ad-slot" });
    var label = el("p", { class: "buytools-ad-label" }, "Advertisement");
    slot.appendChild(label);
    var target = el("div", { class: "buytools-ad-content" });
    slot.appendChild(target);
    var footer = document.querySelector("footer");
    var main = document.querySelector("main");
    if (footer && footer.parentNode) footer.parentNode.insertBefore(slot, footer);
    else if (main) main.appendChild(slot);
    else document.body.appendChild(slot);
    if (nativePages) loadNative(target); else loadBanner(target);
  }
  function showConsent(force) {
    if (document.getElementById("buytools-ad-consent")) return;
    var consent = readConsent();
    if (!force && consent === "accepted") { mountAds(); return; }
    if (!force && consent === "rejected") return;
    var panel = el("aside", { id: "buytools-ad-consent", role: "region", "aria-live": "polite", "aria-label": "Advertising preferences", "aria-describedby": "buytools-ad-consent-description" });
    var copy = el("p", { id: "buytools-ad-consent-description" }, "BuyTools.si uses Adsterra advertising. If you accept, its ad technology may use cookies or similar technologies and process technical data to deliver and measure ads. You can reject and continue using the site.");
    var privacyLink = el("a", { href: "/privacy/", class: "buytools-consent-privacy-link" }, "Read the privacy policy");
    if (preferencesButton) preferencesButton.setAttribute("aria-expanded", "true");
    var actions = el("div", { class: "buytools-consent-actions" });
    var accept = el("button", { type: "button" }, "Accept advertising");
    var reject = el("button", { type: "button" }, "Reject");
    accept.addEventListener("click", function () {
      if (!saveConsent("accepted")) {
        var status = panel.querySelector("#buytools-ad-consent-status");
        if (!status) {
          status = el("p", { id: "buytools-ad-consent-status", role: "status", "aria-live": "polite" });
          panel.insertBefore(status, actions);
        }
        status.textContent = "Your browser blocked saving this choice. Advertising will remain disabled for this visit.";
        return;
      }
      panel.remove();
      if (preferencesButton) preferencesButton.setAttribute("aria-expanded", "false");
      var oldNotice = document.getElementById("buytools-ad-consent-notice");
      if (oldNotice) oldNotice.remove();
      mountAds();
    });
    reject.addEventListener("click", function () {
      var hadAdSlot = !!document.getElementById("buytools-ad-slot");
      var saved = saveConsent("rejected");
      panel.remove();
      if (preferencesButton) preferencesButton.setAttribute("aria-expanded", "false");
      if (!saved && hadAdSlot) {
        var existingSlot = document.getElementById("buytools-ad-slot");
        if (existingSlot) existingSlot.remove();
      }
      if (saved && !consentReadFailed) {
        var oldNotice = document.getElementById("buytools-ad-consent-notice");
        if (oldNotice) oldNotice.remove();
      }
      if (!saved || consentReadFailed) showConsentNotice(hadAdSlot);
      if (saved && hadAdSlot) window.location.reload();
    });
    actions.appendChild(accept); actions.appendChild(reject);
    panel.appendChild(copy); panel.appendChild(privacyLink); panel.appendChild(actions);
    document.body.appendChild(panel);
  }
  function addPreferencesControl() {
    var existing = document.getElementById("buytools-ad-preferences");
    if (existing) { preferencesButton = existing; return; }
    var footer = document.querySelector("footer");
    preferencesButton = el("button", {
      id: "buytools-ad-preferences",
      type: "button",
      "aria-controls": "buytools-ad-consent",
      "aria-expanded": "false"
    }, "Advertising preferences");
    preferencesButton.addEventListener("click", function () { showConsent(true); });
    (footer || document.body).appendChild(preferencesButton);
  }
  function start() {
    if (!document.querySelector("style#buytools-ad-styles")) {
      var style = el("style", { id: "buytools-ad-styles" });
      style.textContent = "#buytools-ad-slot{box-sizing:border-box;width:min(100% - 32px,1000px);margin:28px auto 36px;padding:14px 12px;border:1px solid rgba(150,160,180,.16);border-radius:14px;background:rgba(120,130,150,.035);text-align:center;overflow:hidden;min-height:58px}#buytools-ad-slot .buytools-ad-label{margin:0 0 8px;color:#8992a6;font:10px/1.4 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase}#buytools-ad-slot .buytools-ad-content{display:flex;justify-content:center;align-items:center;max-width:100%;overflow:hidden;min-height:50px}#buytools-ad-slot iframe{max-width:100%;border:0}#buytools-ad-consent{position:fixed;z-index:99999;left:12px;right:12px;bottom:12px;max-width:620px;margin:auto;padding:16px;border:1px solid #596174;border-radius:14px;background:#171b28;color:#f4f6ff;box-shadow:0 8px 36px #0008;font:14px/1.5 system-ui,sans-serif}#buytools-ad-consent p{margin:0 0 12px}#buytools-ad-consent .buytools-consent-privacy-link{display:inline-block;margin:0 0 12px;color:#a5f36b;text-decoration:underline;text-underline-offset:3px}#buytools-ad-consent .buytools-consent-privacy-link:focus-visible{outline:2px solid #a5f36b;outline-offset:3px;border-radius:3px}#buytools-ad-consent .buytools-consent-actions{display:flex;gap:10px;flex-wrap:wrap}#buytools-ad-consent button{border:1px solid #7c879d;border-radius:8px;padding:9px 13px;background:transparent;color:inherit;font:inherit;cursor:pointer}#buytools-ad-consent button:first-child{background:#a5f36b;color:#10150d;border-color:#a5f36b;font-weight:700}#buytools-ad-consent-notice{width:min(100% - 32px,620px);margin:16px auto;padding:12px 14px;border:1px solid #596174;border-radius:10px;background:#171b28;color:#f4f6ff;box-shadow:0 4px 18px #0005;font:13px/1.5 system-ui,sans-serif}#buytools-ad-consent-notice:focus{outline:2px solid #a5f36b;outline-offset:3px}#buytools-ad-preferences{display:inline-block;margin:10px 12px 10px 0;padding:6px 0;border:0;background:transparent;color:inherit;text-decoration:underline;text-underline-offset:3px;font:inherit;cursor:pointer}#buytools-ad-preferences:focus-visible{outline:2px solid #a5f36b;outline-offset:3px;border-radius:3px}@media(max-width:380px){#buytools-ad-slot{width:calc(100% - 16px);padding:10px 4px}}";
      document.head.appendChild(style);
    }
    addPreferencesControl();
    window.addEventListener("storage", handleConsentStorage);
    var openPreferences = /(?:^|[?&])ad-preferences=1(?:&|$)/.test(window.location.search);
    showConsent(openPreferences);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();

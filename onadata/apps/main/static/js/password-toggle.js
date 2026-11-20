/*
 * Adds a Show/Hide button after every password input, so users can check
 * what they typed. Served as a file so it runs under the CSP without a nonce.
 */
(function () {
  "use strict";

  var translate = typeof window.gettext === "function" ? window.gettext : function (text) {
    return text;
  };
  var SHOW = translate("Show");
  var HIDE = translate("Hide");
  var SHOW_LABEL = translate("Show password");
  var HIDE_LABEL = translate("Hide password");

  function setState(input, button, revealed) {
    input.type = revealed ? "text" : "password";
    button.textContent = revealed ? HIDE : SHOW;
    button.setAttribute("aria-label", revealed ? HIDE_LABEL : SHOW_LABEL);
    button.setAttribute("aria-pressed", revealed ? "true" : "false");
  }

  function addToggle(input) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "btn password-toggle";
    button.style.marginLeft = "4px";
    if (input.id) {
      button.setAttribute("aria-controls", input.id);
    }
    setState(input, button, false);
    button.addEventListener("click", function () {
      setState(input, button, input.type === "password");
    });
    input.insertAdjacentElement("afterend", button);
  }

  function addToggles() {
    var inputs = document.querySelectorAll('input[type="password"]');
    Array.prototype.forEach.call(inputs, addToggle);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", addToggles);
  } else {
    addToggles();
  }
})();

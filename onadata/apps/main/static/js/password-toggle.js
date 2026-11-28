/*
 * Adds an eye button inside the end of every password input, so users can
 * check what they typed. Served as a file so it runs under the CSP without a
 * nonce, and lays itself out with inline styles so it needs no stylesheet.
 *
 * The icon paths are Lucide's "eye" and "eye-off", used under this licence:
 *
 * ISC License
 *
 * Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as
 * part of Feather (MIT). All other copyright (c) for Lucide are held by
 * Lucide Contributors 2022.
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */
(function () {
  "use strict";

  var SVG_NS = "http://www.w3.org/2000/svg";
  // Named gettext so makemessages -d djangojs extracts the labels.
  var gettext = typeof window.gettext === "function" ? window.gettext : function (text) {
    return text;
  };
  var SHOW_LABEL = gettext("Show password");
  var HIDE_LABEL = gettext("Hide password");
  var EYE = [
    ["path", { d: "M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" }],
    ["circle", { cx: "12", cy: "12", r: "3" }]
  ];
  var EYE_OFF = [
    ["path", { d: "M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49" }],
    ["path", { d: "M14.084 14.158a3 3 0 0 1-4.242-4.242" }],
    ["path", { d: "M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143" }],
    ["path", { d: "m2 2 20 20" }]
  ];
  var SVG_ATTRIBUTES = {
    width: "16",
    height: "16",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "2",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "aria-hidden": "true",
    focusable: "false"
  };

  function svgElement(name, attributes) {
    var element = document.createElementNS(SVG_NS, name);
    Object.keys(attributes).forEach(function (key) {
      element.setAttribute(key, attributes[key]);
    });
    return element;
  }

  function icon(shapes) {
    var svg = svgElement("svg", SVG_ATTRIBUTES);
    shapes.forEach(function (shape) {
      svg.appendChild(svgElement(shape[0], shape[1]));
    });
    return svg;
  }

  function setState(input, button, revealed) {
    input.type = revealed ? "text" : "password";
    while (button.firstChild) {
      button.removeChild(button.firstChild);
    }
    button.appendChild(icon(revealed ? EYE_OFF : EYE));
    button.setAttribute("aria-label", revealed ? HIDE_LABEL : SHOW_LABEL);
  }

  var FIELD_CLASS = "password-toggle-field";
  var BUTTON_SIZE = "28px";
  var BUTTON_INSET = "4px";

  function setStyles(element, styles) {
    Object.keys(styles).forEach(function (property) {
      element.style.setProperty(property, styles[property]);
    });
  }

  function fillsParent(input) {
    var parent = input.parentElement;
    var style = window.getComputedStyle(parent);
    var available = parent.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    return input.offsetWidth >= available - 1;
  }

  // A flex wrapper avoids the line box an inline-block input leaves below it.
  // The input's margins move to the wrapper, so the wrapper's box is the
  // field's and the button centres on it.
  function wrapField(input, fills) {
    var style = window.getComputedStyle(input);
    var focused = document.activeElement === input;
    var wrapper = document.createElement("span");
    wrapper.className = FIELD_CLASS;
    setStyles(wrapper, {
      position: "relative",
      display: /^(block|flex|grid|table|list-item)$/.test(style.display) ? "flex" : "inline-flex",
      "inline-size": fills ? "100%" : "fit-content",
      "max-inline-size": "100%",
      margin: style.marginTop + " " + style.marginRight + " " + style.marginBottom + " " + style.marginLeft
    });
    input.style.setProperty("margin", "0");
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);
    // Moving a focused element blurs it, which would undo autofocus.
    if (focused) {
      input.focus();
    }
    return wrapper;
  }

  function focusedByKeyboard(button) {
    try {
      return button.matches(":focus-visible");
    } catch (error) {
      // Browsers that predate :focus-visible throw on the selector.
      return true;
    }
  }

  function showFocusRing(button) {
    if (focusedByKeyboard(button)) {
      setStyles(button, { outline: "2px solid currentColor", "outline-offset": "1px" });
    }
  }

  function styleButton(button) {
    setStyles(button, {
      position: "absolute",
      "inset-inline-end": BUTTON_INSET,
      "inset-block-start": "50%",
      transform: "translateY(-50%)",
      display: "inline-flex",
      "align-items": "center",
      "justify-content": "center",
      "min-inline-size": BUTTON_SIZE,
      "min-block-size": BUTTON_SIZE,
      "inline-size": "auto",
      margin: "0",
      padding: "0",
      border: "0",
      "border-radius": "4px",
      background: "transparent",
      "box-shadow": "none",
      color: "inherit",
      cursor: "pointer",
      outline: "none"
    });
    button.addEventListener("focus", function () {
      showFocusRing(button);
    });
    button.addEventListener("blur", function () {
      button.style.setProperty("outline", "none");
    });
  }

  // Room for the button comes out of the field's width, so it stays as wide
  // as before. A field that doesn't fill its parent keeps its width in px,
  // since a percentage would resolve against the shrink-to-fit wrapper.
  function padInputEnd(input, fills) {
    var before = input.offsetWidth;
    var padding = window.getComputedStyle(input).getPropertyValue("padding-inline-end") || "0px";
    input.style.setProperty(
      "padding-inline-end",
      "calc(" + padding + " + " + BUTTON_SIZE + " + " + BUTTON_INSET + ")"
    );
    var growth = input.offsetWidth - before;
    if (!fills || growth > 0) {
      var width = parseFloat(window.getComputedStyle(input).width);
      input.style.setProperty("width", width - growth + "px");
    }
  }

  // Edge draws its own reveal button in password inputs. A constructed sheet
  // hides it without an inline style element, which the CSP would block.
  function hideNativeReveal() {
    try {
      var sheet = new CSSStyleSheet();
      sheet.replaceSync("input::-ms-reveal { display: none; }");
      document.adoptedStyleSheets = document.adoptedStyleSheets.concat(sheet);
    } catch (error) {
      // Browsers without constructed sheets have no reveal button of their own.
    }
  }

  // A revealed password is ordinary text. These stop cloud spellcheckers
  // sending it off the device and autocorrect changing it, though some mobile
  // keyboards may still learn it.
  var PRIVATE_TEXT = { spellcheck: "false", autocorrect: "off", autocapitalize: "none" };

  function keepPrivate(input) {
    Object.keys(PRIVATE_TEXT).forEach(function (name) {
      input.setAttribute(name, PRIVATE_TEXT[name]);
    });
  }

  function addToggle(input) {
    // A hidden field would leave its button showing on its own.
    if (input.parentElement.classList.contains(FIELD_CLASS) || window.getComputedStyle(input).display === "none") {
      return;
    }
    keepPrivate(input);
    var button = document.createElement("button");
    button.type = "button";
    button.className = "password-toggle";
    if (input.id) {
      button.setAttribute("aria-controls", input.id);
    }
    styleButton(button);
    setState(input, button, false);
    button.addEventListener("click", function () {
      setState(input, button, input.type === "password");
    });
    // A field still revealed at submit, or when the page is left, would be
    // kept as plain text in autofill history or a restored page.
    function hide() {
      setState(input, button, false);
    }
    if (input.form) {
      input.form.addEventListener("submit", hide);
    }
    window.addEventListener("pagehide", hide);
    var fills = fillsParent(input);
    padInputEnd(input, fills);
    wrapField(input, fills).appendChild(button);
  }

  function addToggles() {
    var inputs = document.querySelectorAll('input[type="password"]');
    if (inputs.length) {
      hideNativeReveal();
    }
    Array.prototype.forEach.call(inputs, addToggle);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", addToggles);
  } else {
    addToggles();
  }
})();

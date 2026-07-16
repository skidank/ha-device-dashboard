(() => {
  // Injected once as an ES module, so it runs once per full page load; this guard is a
  // backstop (and resets on reload). SPA navigation never re-runs the module — that is
  // what prevents a "bounce" when the user manually opens another dashboard.
  if (window.__deviceDashboardRouted) return;

  // Capture the path the app/browser actually opened with, NOW — before the frontend does
  // its client-side defaultPanel routing. This is the true launch page and is what we
  // decide from, so we can redirect without first waiting for (and painting) the default
  // panel. A base-URL launch is "" here; a deep link (e.g. a notification) is the linked
  // path. If the module happens to load after routing, this is the default panel instead —
  // still handled, since the default panel is in the landing set below.
  const entrySeg = location.pathname.replace(/^\/+/, "").split("/")[0];

  const classify = (ua) => {
    if (/io\.robbie\.HomeAssistant/i.test(ua)) return "ios_app";
    if (/io\.homeassistant\.companion\.android/i.test(ua)) return "android_app";
    if (/Mobi|Android|iPhone|iPad/i.test(ua)) return "mobile_web";
    return "desktop";
  };

  // setTimeout (not rAF) so it also ticks in a backgrounded/throttled tab; bounded so it
  // never spins forever if the element never appears.
  const waitForHass = (timeoutMs = 10000) =>
    new Promise((resolve, reject) => {
      const start = performance.now();
      const tick = () => {
        const el = document.querySelector("home-assistant");
        if (el?.hass?.connection) return resolve(el.hass);
        if (performance.now() - start > timeoutMs) return reject(new Error("no hass"));
        setTimeout(tick, 100);
      };
      tick();
    });

  const run = async () => {
    const hass = await waitForHass();
    const cfg = await hass.connection.sendMessagePromise({
      type: "device_dashboard/get_config",
    });
    const cls = classify(navigator.userAgent);
    const target = cfg.mappings?.[cls];
    if (!target) {
      console.info("[device_dashboard] no mapping for", cls, "-", cfg.mappings);
      return; // no mapping → respect the user's normal default
    }

    // A launch enters on the base URL ("") or, if the module loaded after routing, on the
    // user's default panel (resolved as the frontend does). Treat those — plus "lovelace"
    // and any configured landing_paths — as redirect-eligible, so a launch redirects but a
    // deep link to another dashboard does not.
    const defaultPanel =
      hass.userData?.default_panel || hass.systemData?.default_panel || "lovelace";
    const landing = new Set(["", "lovelace", defaultPanel, ...(cfg.landing_paths || [])]);

    console.info("[device_dashboard]", {
      class: cls,
      target,
      entrySeg,
      defaultPanel,
      eligible: landing.has(entrySeg) && entrySeg !== target,
    });

    if (entrySeg === target) return; // already there
    if (!landing.has(entrySeg)) return; // deep link → leave alone

    // Full navigation (not history.replaceState + a location-changed event) so the target
    // loads fresh and load-time frontend plugins initialize on it — e.g. kiosk-mode, which
    // hides the HA chrome via an ON_LOVELACE_PANEL_LOAD hook and does NOT re-run on a soft
    // in-app nav. location.replace adds no history entry; on the fresh load this module
    // re-runs and no-ops (entrySeg === target).
    window.__deviceDashboardRouted = true;
    location.replace("/" + target);
  };

  run().catch(() => {});
})();

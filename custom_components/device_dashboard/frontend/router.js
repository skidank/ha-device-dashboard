(() => {
  // Injected once as an ES module, so it runs once per full page load; this guard is a
  // backstop (and resets on reload). SPA navigation never re-runs the module — that is
  // what prevents a "bounce" when the user manually opens another dashboard.
  if (window.__deviceDashboardRouted) return;

  // Entry path captured synchronously, BEFORE the frontend runs its own defaultPanel
  // navigation. This is the race-proof "was this a fresh launch?" signal: a launch enters
  // at the base URL "" and a deep link enters at its own dashboard slug. Unlike the
  // settled-path + default_panel check below it never depends on hass.userData having
  // loaded, so it can't miss a launch redirect on a cold start (see liveHass).
  const entrySeg = location.pathname.replace(/^\/+/, "").split("/")[0];

  const classify = (ua) => {
    if (/io\.robbie\.HomeAssistant/i.test(ua)) return "ios_app";
    if (/io\.homeassistant\.companion\.android/i.test(ua)) return "android_app";
    // iPadOS Safari defaults to a desktop (macOS) UA with no iPad/Mobi token; detect that
    // via touch support so an iPad browser is treated as mobile rather than desktop.
    const tabletOrPhone =
      /Mobi|Android|iPhone|iPad/i.test(ua) ||
      (/Macintosh/i.test(ua) && (navigator.maxTouchPoints || 0) > 1);
    if (tabletOrPhone) return "mobile_web";
    return "desktop";
  };

  // The <home-assistant> element replaces its `hass` object on every update (HA's hass is
  // immutable), so a reference captured once goes stale. Read the LIVE one at decision
  // time — critically for userData.default_panel, which starts `undefined` and is populated
  // asynchronously AFTER the connection exists (via subscribeFrontendUserData), i.e. often
  // after waitForHass has already resolved. Reading a captured snapshot instead was the
  // cause of intermittently-missed launch redirects.
  const liveHass = () => document.querySelector("home-assistant")?.hass || null;

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

  // Let the frontend finish its own defaultPanel navigation before we decide, so a real
  // dashboard renders before the redirect (smoother than reloading straight from a loading
  // splash). Wait for the path to leave "/", capped so we still act if the landing is root.
  const settle = () =>
    new Promise((resolve) => {
      let tries = 0;
      const tick = () => {
        const seg = location.pathname.replace(/^\/+/, "").split("/")[0];
        if (seg !== "" || tries++ > 8) return resolve();
        setTimeout(tick, 50);
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
    // A dashboard url_path is a single slug segment. Validate before using it in a
    // navigation so a malformed/hostile value can't become a protocol-relative
    // ("//evil.com") off-origin redirect.
    if (!target || !/^[a-z0-9][a-z0-9_-]*$/i.test(target)) return;

    await settle(); // wait out the frontend's defaultPanel routing

    // Resolve the default panel from the LIVE hass (see liveHass): the frontend routes
    // "/" -> "/<default_panel>" using userData, and settle() only returns once that routing
    // has happened, so by now userData.default_panel is loaded. Reading the stale captured
    // snapshot here was the bug — its userData was still undefined, so the landing set fell
    // back to "lovelace" and a launch onto a *custom* default panel looked like a deep link
    // and was never redirected (intermittently, depending on load timing).
    const h = liveHass() || hass;
    const defaultPanel =
      h.userData?.default_panel || h.systemData?.default_panel || "lovelace";
    const seg = location.pathname.replace(/^\/+/, "").split("/")[0];

    // A fresh launch lands on the user's default panel (resolved as the frontend does), or
    // the base URL "" before routing. Treat those — plus the built-in defaults
    // "lovelace"/"home" — as redirect-eligible, so a launch redirects but a deep link to
    // another dashboard does not.
    const landing = new Set(["", "lovelace", "home", defaultPanel]);

    if (seg === target) return; // already there
    // Redirect only from a landing page. A fresh launch enters on a landing (entrySeg,
    // captured before routing) and settles on one (seg); a deep link enters and stays on
    // its own slug. Requiring EITHER path to be a landing keeps launches redirecting even
    // if the live default_panel is momentarily unavailable, while still leaving genuine
    // deep links alone.
    if (!landing.has(entrySeg) && !landing.has(seg)) return; // deep link → leave alone

    // Full navigation (not history.replaceState + a location-changed event) so the target
    // loads fresh and load-time frontend plugins initialize on it — e.g. kiosk-mode, which
    // hides the HA chrome via an ON_LOVELACE_PANEL_LOAD hook and does NOT re-run on a soft
    // in-app nav. Resolve against our own origin and never leave it; location.replace adds
    // no history entry, and on the fresh load this module re-runs and no-ops (seg === target).
    const dest = new URL("/" + target, location.origin);
    if (dest.origin !== location.origin) return;
    window.__deviceDashboardRouted = true;
    location.replace(dest.pathname);
  };

  run().catch((e) => console.debug("[device_dashboard] skipped:", e?.message || e));
})();

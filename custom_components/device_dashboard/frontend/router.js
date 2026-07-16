(() => {
  // Injected once as an ES module, so it runs once per full page load; this guard is a
  // backstop (and resets on reload). SPA navigation never re-runs the module — that is
  // what prevents a "bounce" when the user manually opens another dashboard.
  if (window.__deviceDashboardRouted) return;

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

  // Let the frontend finish its own defaultPanel navigation before we decide, else it may
  // run *after* us and override the redirect. Wait for the path to leave "/", capped so we
  // still act if the landing genuinely is root.
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
    if (!target) {
      console.info("[device_dashboard] no mapping for", cls, "-", cfg.mappings);
      return; // no mapping → respect the user's normal default
    }

    await settle(); // wait out the frontend's defaultPanel routing

    // The page a fresh launch lands on is the user's default panel (resolved exactly like
    // the frontend does). Treat it — plus "" and "lovelace" and any configured
    // landing_paths — as redirect-eligible, so a launch redirects but a deep link to
    // another dashboard does not.
    const defaultPanel =
      hass.userData?.default_panel || hass.systemData?.default_panel || "lovelace";
    const seg = location.pathname.replace(/^\/+/, "").split("/")[0];
    const landing = new Set(["", "lovelace", defaultPanel, ...(cfg.landing_paths || [])]);

    console.info("[device_dashboard]", {
      class: cls,
      target,
      seg,
      defaultPanel,
      eligible: landing.has(seg) && seg !== target,
    });

    if (seg === target) return; // already there
    if (!landing.has(seg)) return; // deep link → leave alone

    window.__deviceDashboardRouted = true;
    history.replaceState(null, "", "/" + target);
    window.dispatchEvent(new Event("location-changed"));
  };

  run().catch(() => {});
})();

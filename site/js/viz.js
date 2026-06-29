/* ============================================================
   viz.js: fills the hero "live climate data" card from
   site/data/era5_daily.json (built by scripts/process_era5.py).
   The heavy interactive chart was retired in favor of linking to the
   live Climate Dashboard; this keeps just the headline numbers.
   ============================================================ */
(function () {
  "use strict";

  var DATA_URL = "data/era5_daily.json";

  function set(id, txt) { var el = document.getElementById(id); if (el) el.textContent = txt; }

  function fill(d) {
    var s = d.stats || {};
    if (d.latest) {
      set("heroAnom", "+" + d.latest.anom.toFixed(2) + "°C");
      set("heroDate", d.latest.date);
    }
    if (s.hottest_year) set("heroHottest", s.hottest_year.year + " · +" + s.hottest_year.anom.toFixed(2) + "°C");
    if (s.trailing_365_mean != null) set("heroTrailing", "+" + s.trailing_365_mean.toFixed(2) + "°C");
  }

  function init() {
    fetch(DATA_URL)
      .then(function (r) { if (!r.ok) throw new Error("era5 " + r.status); return r.json(); })
      .then(fill)
      .catch(function (e) { console.error("ERA5 data failed to load:", e); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

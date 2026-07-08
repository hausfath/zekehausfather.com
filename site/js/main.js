/* ============================================================
   main.js: feeds (Climate Brink / Carbon Brief / media), nav,
   reveal-on-scroll, full publication list, social fallback.
   ============================================================ */
(function () {
  "use strict";

  /* ---------- helpers ---------- */
  function fmtDate(iso, opts) {
    const d = new Date(iso + (iso.length === 10 ? "T12:00:00" : ""));
    if (isNaN(d)) return { day: iso, my: "" };
    return {
      full: d.toLocaleDateString("en-US", opts || { year: "numeric", month: "short", day: "numeric" }),
      day: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      my: d.toLocaleDateString("en-US", { year: "numeric" }),
    };
  }
  function esc(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }
  function getJSON(url) { return fetch(url).then((r) => { if (!r.ok) throw new Error(url + " " + r.status); return r.json(); }); }

  /* ---------- blog feeds ---------- */
  function renderPosts(el, posts, opts) {
    if (!el) return;
    if (!posts || !posts.length) { el.innerHTML = '<p class="feed__loading">No posts available.</p>'; return; }
    el.innerHTML = posts.slice(0, opts.limit || 6).map((p) => {
      const dt = fmtDate(p.date);
      const tag = p.category ? `<span class="post__tag">${esc(p.category)}</span>` : "";
      return `<a class="post" href="${esc(p.url)}" target="_blank" rel="noopener">
        <span class="post__date">${dt.day}<span>${dt.my}</span></span>
        <span class="post__main">
          <span class="post__title">${esc(p.title)}</span>
          ${p.description ? `<p class="post__desc">${esc(p.description)}</p>` : ""}
          ${tag}
        </span>
      </a>`;
    }).join("");
  }

  function loadFeeds() {
    getJSON("data/climate_brink.json")
      .then((d) => renderPosts(document.getElementById("feedBrink"), d.posts, { limit: 5 }))
      .catch(() => { const e = document.getElementById("feedBrink"); if (e) e.innerHTML = '<p class="feed__loading">Visit The Climate Brink ↗</p>'; });

    getJSON("data/carbon_brief.json")
      .then((d) => renderPosts(document.getElementById("feedCarbon"), d.posts, { limit: 5 }))
      .catch(() => { const e = document.getElementById("feedCarbon"); if (e) e.innerHTML = '<p class="feed__loading">Visit Carbon Brief ↗</p>'; });
  }

  /* ---------- media coverage ---------- */
  function loadMedia() {
    const el = document.getElementById("mediaList");
    if (!el) return;
    getJSON("data/media.json").then((d) => {
      const items = (d.items || []).slice().sort((a, b) => (b.date || "").localeCompare(a.date || ""));
      if (!items.length) { el.innerHTML = '<p class="feed__loading">No coverage listed.</p>'; return; }
      el.innerHTML = items.map((m) => {
        const dt = fmtDate(m.date);
        const inner = `
          <span class="media-item__date">${dt.full || m.date}</span>
          <span class="media-item__main">
            <span class="media-item__title">${esc(m.title)}</span>
            ${m.note ? `<p class="media-item__note">${esc(m.note)}</p>` : ""}
          </span>
          <span class="media-item__outlet">${esc(m.outlet)}</span>`;
        return m.url
          ? `<a class="media-item" href="${esc(m.url)}" target="_blank" rel="noopener">${inner}</a>`
          : `<div class="media-item">${inner}</div>`;
      }).join("");
    }).catch(() => { el.innerHTML = '<p class="feed__loading">Coverage could not be loaded.</p>'; });
  }

  /* ---------- GitHub: recently updated repos ---------- */
  function loadGithub() {
    const el = document.getElementById("ghRepos");
    if (!el) return;
    getJSON("data/github.json").then((d) => {
      const repos = (d.repos || []).slice(0, 4);
      if (!repos.length) throw new Error("no repos");
      el.innerHTML = repos.map((r) => {
        const upd = r.updated ? new Date(r.updated + "T12:00:00") : null;
        const updStr = upd && !isNaN(upd) ? upd.toLocaleDateString("en-US", { month: "short", year: "numeric" }) : "";
        const meta = [r.language, r.stars ? "★ " + r.stars : "", updStr].filter(Boolean).join(" · ");
        return `<li><a class="ghrepo" href="${esc(r.url)}" target="_blank" rel="noopener">
          <span class="ghrepo__top"><span class="ghrepo__name">${esc(r.name)}</span><span class="ghrepo__meta">${esc(meta)}</span></span>
          ${r.description ? `<span class="ghrepo__desc">${esc(r.description)}</span>` : ""}
        </a></li>`;
      }).join("");
    }).catch(() => {
      el.innerHTML = '<li class="ghcard__loading"><a href="https://github.com/hausfath" target="_blank" rel="noopener">View repositories on GitHub ↗</a></li>';
    });
  }

  /* ---------- Bluesky feed (live, public API — CORS-enabled, no auth) ---------- */
  function loadSocial() {
    const el = document.getElementById("socialEmbed");
    if (!el) return;
    // Use the stable DID (not the handle) so the feed keeps working if the
    // Bluesky handle changes (e.g. to a domain handle like @zekehausfather.com).
    const DID = "did:plc:r5ofoghdcbtjqiujqpvja4uh";
    const API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed" +
      "?actor=" + DID + "&limit=20&filter=posts_no_replies";
    fetch(API)
      .then((r) => { if (!r.ok) throw new Error("bsky " + r.status); return r.json(); })
      .then((d) => {
        const posts = (d.feed || [])
          .filter((it) => !it.reason)                 // drop reposts; keep his own posts
          .map((it) => it.post)
          .filter((p) => p && p.record && p.record.text)
          .slice(0, 4);
        if (!posts.length) throw new Error("no posts");
        el.innerHTML = posts.map((p) => {
          const rkey = (p.uri || "").split("/").pop();
          const handle = (p.author && p.author.handle) || DID;
          const url = "https://bsky.app/profile/" + handle + "/post/" + rkey;
          const dt = fmtDate((p.record.createdAt || "").slice(0, 10));
          const stats = [
            p.repostCount ? "↻ " + p.repostCount : "",
            p.likeCount ? "♥ " + p.likeCount : "",
          ].filter(Boolean).join("  ");
          return `<a class="bskypost" href="${url}" target="_blank" rel="noopener">
            <span class="bskypost__text">${esc(p.record.text)}</span>
            <span class="bskypost__meta">${dt.full || ""}${stats ? " · " + stats : ""}</span>
          </a>`;
        }).join("");
      })
      .catch(() => {
        el.innerHTML = '<a class="bskypost bskypost--fallback" href="https://bsky.app/profile/' + DID + '" target="_blank" rel="noopener">See the latest on Bluesky ↗</a>';
      });
  }

  /* ---------- full publications list ----------
     Fallback only. The live list is data/publications.json, refreshed weekly
     from OpenAlex by scripts/update_publications.py. This hardcoded copy is
     shown if that fetch fails. ---------- */
  var PUBLICATIONS = [
    [2026, "Indicators of Global Climate Change 2025: annual update of key indicators of the state of the climate system and human influence", "Earth System Science Data", "https://essd.copernicus.org/articles/18/3889/2026/"],
    [2026, "The value of reversible carbon storage in a zero-emissions world (Mayer, Hausfather, Pett-Ridge, Slessarev)", "Environmental Science &amp; Technology", "https://pubs.acs.org/doi/10.1021/acs.est.6c00333"],
    [2026, "Ocean heat content sets another record in 2025 (Pan, Cheng, Abraham, ... Hausfather)", "Advances in Atmospheric Sciences"],
    [2025, "Indicators of Global Climate Change 2024: annual update of key indicators of the state of the climate system and human influence", "Earth System Science Data", "https://essd.copernicus.org/articles/17/2641/2025/"],
    [2025, "An assessment of current policy scenarios over the 21st century and the reduced plausibility of high-emissions pathways", "Dialogues on Climate Change", "https://doi.org/10.1177/29768659241304854"],
    [2025, "Record high temperatures in the ocean in 2024", "Advances in Atmospheric Sciences"],
    [2024, "Durability of carbon dioxide removal is critical for Paris climate goals (Brunner, Hausfather, Knutti)", "Communications Earth &amp; Environment"],
    [2024, "A perspective on the next generation of Earth system model scenarios: towards representative emission pathways (REPs)", "Geoscientific Model Development"],
    [2023, "Ch. 2 Climate Trends, Fifth U.S. National Climate Assessment", "USGCRP", "https://nca2023.globalchange.gov/chapter/2/"],
    [2023, "Ten new insights in climate science 2023", "Global Sustainability"],
    [2023, "Mechanisms and impacts of climate tipping elements", "Reviews of Geophysics"],
    [2023, "Materials demand for electricity in climate mitigation scenarios", "Joule"],
    [2022, "Improved quantification of the rate of ocean warming", "Journal of Climate"],
    [2022, "Net-zero commitments could limit warming to below 2°C (Hausfather &amp; Moore)", "Nature", "https://www.nature.com/articles/d41586-022-01129-9"],
    [2022, "Climate simulations: recognize the 'hot model' problem", "Nature", "https://www.nature.com/articles/d41586-022-01192-2"],
    [2022, "The Chinese carbon-neutral goal: challenges and prospects", "Advances in Atmospheric Sciences"],
    [2021, "Climate Change 2021: The Physical Science Basis (IPCC AR6 WGI, contributing author)", "Cambridge University Press", "https://www.ipcc.ch/report/ar6/wg1/"],
    [2020, "The Berkeley Earth land/ocean temperature record (Rohde &amp; Hausfather)", "Earth System Science Data", "https://essd.copernicus.org/articles/12/3469/2020/"],
    [2020, "RCP8.5 is a problematic scenario for near-term emissions (Hausfather &amp; Peters)", "PNAS", "https://www.pnas.org/doi/10.1073/pnas.2007117117"],
    [2020, "An assessment of Earth's climate sensitivity using multiple lines of evidence", "Reviews of Geophysics", "https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2019RG000678"],
    [2020, "Emissions – the 'business as usual' story is misleading (Hausfather &amp; Peters)", "Nature", "https://www.nature.com/articles/d41586-020-00177-3"],
    [2019, "Evaluating the performance of past climate model projections", "Geophysical Research Letters", "https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2019GL085378"],
    [2019, "Contribution of the land sector to a 1.5°C world", "Nature Climate Change"],
    [2019, "A limited role for unforced internal variability in twentieth-century warming", "Journal of Climate"],
    [2019, "How fast are the oceans warming?", "Science", "https://www.science.org/doi/10.1126/science.aav7619"],
    [2018, "The potential of agricultural land management to lower global surface temperatures", "Science Advances"],
    [2018, "Towards a global land surface climate fiducial reference measurements network", "International Journal of Climatology"],
    [2018, "Evaluating biases in sea surface temperature records using coastal weather stations", "Quarterly Journal of the Royal Meteorological Society"],
    [2017, "Assessing recent warming using instrumentally homogeneous sea surface temperature records", "Science Advances", "https://www.science.org/doi/10.1126/sciadv.1601207"],
    [2016, "Evaluating the impact of U.S. Historical Climatology Network homogenization using the U.S. Climate Reference Network", "Geophysical Research Letters"],
    [2016, "Reassessing changes in diurnal temperature range", "Journal of Geophysical Research: Atmospheres"],
    [2016, "Climate benefits of natural gas as a bridge fuel and potential delay of near-zero energy systems", "Applied Energy"],
    [2015, "Bounding the climate viability of natural gas as a bridge fuel to displace coal", "Energy Policy"],
    [2015, "Robust comparison of climate models with observations using blended land air and ocean sea surface temperatures", "Geophysical Research Letters"],
    [2015, "Misdiagnosis of Earth climate sensitivity based on energy balance model results", "Science Bulletin"],
    [2014, "A regional model of direct and indirect rebound effects", "Environmental Research Letters"],
    [2014, "A framework for benchmarking of homogenisation algorithm performance on the global scale", "Geoscientific Instrumentation, Methods and Data Systems"],
    [2013, "Quantifying the effect of urbanization on U.S. Historical Climatology Network temperature records", "Journal of Geophysical Research"],
    [2012, "Metal lost and found: dissipative uses and releases of copper in the United States 1975–2000", "Science of the Total Environment"],
    [2010, "A high-resolution statistical model of residential energy end-use characteristics for the United States", "Journal of Industrial Ecology"],
    [2005, "India's shark trade: an analysis of Indian shark fisheries based on shark fin exports", "Maritime Studies"],
  ];

  function renderPubList(ol, rows) {
    ol.innerHTML = rows.map((p) => {
      const t = p.url ? `<a href="${p.url}" target="_blank" rel="noopener"><b>${p.title}</b></a>` : `<b>${p.title}</b>`;
      const venue = p.venue ? ` <em>${p.venue}</em>.` : "";
      return `<li><span class="py">${p.year}</span><span class="pt">${t}.${venue}</span></li>`;
    }).join("");
  }

  function buildFullPubs() {
    const ol = document.getElementById("pubsFull");
    const btn = document.getElementById("pubsToggle");
    if (!ol || !btn) return;
    // Render the built-in list immediately, then upgrade to the auto-refreshed
    // OpenAlex list (data/publications.json) when it loads. Falls back silently
    // if the fetch fails, so the section always shows something.
    renderPubList(ol, PUBLICATIONS.map((p) => ({ year: p[0], title: p[1], venue: p[2], url: p[3] || "" })));
    getJSON("data/publications.json")
      .then((d) => { if (d && d.publications && d.publications.length) renderPubList(ol, d.publications); })
      .catch(() => {});
    btn.addEventListener("click", () => {
      const open = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!open));
      ol.hidden = open;
      btn.firstChild.textContent = open ? "Show full publication list " : "Hide full publication list ";
    });
  }

  /* ---------- nav: scroll state, active link, mobile toggle ---------- */
  function initNav() {
    const nav = document.getElementById("nav");
    const toggle = document.getElementById("navToggle");
    const links = Array.from(document.querySelectorAll(".nav__links a"));

    const onScroll = () => { nav.classList.toggle("is-scrolled", window.scrollY > 20); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });

    if (toggle) toggle.addEventListener("click", () => nav.classList.toggle("is-open"));
    links.forEach((a) => a.addEventListener("click", () => nav.classList.remove("is-open")));

    // scroll-spy
    const sections = links
      .map((a) => document.querySelector(a.getAttribute("href")))
      .filter(Boolean);
    const spy = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          links.forEach((a) => a.classList.toggle("is-active", a.getAttribute("href") === "#" + e.target.id));
        }
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    sections.forEach((s) => spy.observe(s));
  }

  /* ---------- reveal on scroll ---------- */
  function initReveal() {
    const els = document.querySelectorAll("[data-reveal]");
    if (!("IntersectionObserver" in window) || !els.length) { els.forEach((e) => e.classList.add("is-in")); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.05 });
    els.forEach((e) => io.observe(e));
  }

  /* ---------- contact modal (email assembled at runtime, never in source) ---------- */
  function initContact() {
    const modal = document.getElementById("contactModal");
    const openBtn = document.getElementById("contactBtn");
    if (!modal || !openBtn || typeof modal.showModal !== "function") return;

    const user = "hausfath", domain = "gmail.com";
    const addr = user + "@" + domain;
    const link = document.getElementById("contactEmail");
    if (link) { link.href = "mailto:" + addr; link.textContent = addr; }

    const close = () => modal.close();
    openBtn.addEventListener("click", () => modal.showModal());
    const closeBtn = document.getElementById("contactClose");
    if (closeBtn) closeBtn.addEventListener("click", close);
    // click on backdrop closes
    modal.addEventListener("click", (e) => { if (e.target === modal) close(); });

    const copyBtn = document.getElementById("contactCopy");
    if (copyBtn) copyBtn.addEventListener("click", () => {
      const done = () => {
        const orig = copyBtn.textContent;
        copyBtn.textContent = "Copied ✓"; copyBtn.classList.add("is-copied");
        setTimeout(() => { copyBtn.textContent = orig; copyBtn.classList.remove("is-copied"); }, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(addr).then(done, () => {});
      } else {
        const t = document.createElement("textarea");
        t.value = addr; document.body.appendChild(t); t.select();
        try { document.execCommand("copy"); done(); } catch (e) {}
        document.body.removeChild(t);
      }
    });
  }

  /* ---------- init ---------- */
  function init() {
    const y = document.getElementById("year"); if (y) y.textContent = new Date().getFullYear();
    loadFeeds();
    loadMedia();
    loadGithub();
    loadSocial();
    buildFullPubs();
    initNav();
    initReveal();
    initContact();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

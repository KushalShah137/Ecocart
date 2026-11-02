/* EcoCart front-end behaviour: flash messages, nav toggle, AJAX cart, Eco Swap slider, charts. */
(function () {
  const CSRF = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const fmtINR = (v) => "₹" + Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });

  // ---- flash messages ----------------------------------------------------------
  function flash(message, kind = "info") {
    let wrap = document.querySelector(".flash-wrap");
    if (!wrap) { wrap = document.createElement("div"); wrap.className = "flash-wrap"; document.body.appendChild(wrap); }
    const el = document.createElement("div");
    el.className = `flash flash-${kind}`;
    el.innerHTML = `<span>${message}</span><button aria-label="Dismiss">×</button>`;
    el.querySelector("button").onclick = () => el.remove();
    wrap.appendChild(el);
    setTimeout(() => el.remove(), 5000);
  }
  window.ecoFlash = flash;
  document.querySelectorAll(".flash").forEach((el) => {
    el.querySelector("button")?.addEventListener("click", () => el.remove());
    setTimeout(() => el.remove(), 6000);
  });

  // ---- mobile nav --------------------------------------------------------------
  document.querySelector(".nav-toggle")?.addEventListener("click", () => document.querySelector(".nav").classList.toggle("open"));

  // ---- JSON helper -------------------------------------------------------------
  async function post(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": CSRF, "X-Requested-With": "fetch", "Accept": "application/json" },
      body: JSON.stringify(Object.assign({ _csrf: CSRF }, body)),
    });
    if (res.status === 401) { window.location = "/login?next=" + encodeURIComponent(location.pathname); return null; }
    return res.json();
  }

  // ---- add to cart (AJAX, falls back to the form if JS is disabled) ---------------
  document.querySelectorAll("form[data-add-to-cart]").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = form.querySelector("button[type=submit]");
      const original = btn.innerHTML;
      btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>';
      try {
        const data = await post(form.action, { product_id: form.product_id.value, quantity: form.quantity ? form.quantity.value : 1 });
        if (!data) return;
        flash(data.message, data.ok ? "success" : "error");
        if (data.ok) document.querySelectorAll("[data-cart-count]").forEach((n) => { n.textContent = data.count; n.hidden = data.count === 0; });
      } catch (err) { flash("Could not add to cart. Please try again.", "error"); }
      finally { btn.disabled = false; btn.innerHTML = original; }
    });
  });

  // ---- cart page quantity controls --------------------------------------------------
  const cartPage = document.querySelector("[data-cart-page]");
  if (cartPage) {
    const refresh = (cart) => {
      cartPage.querySelector("[data-subtotal]").textContent = fmtINR(cart.subtotal);
      cartPage.querySelector("[data-shipping]").textContent = cart.shipping ? fmtINR(cart.shipping) : "Free";
      cartPage.querySelector("[data-total]").textContent = fmtINR(cart.total);
      document.querySelectorAll("[data-cart-count]").forEach((n) => { n.textContent = cart.count; n.hidden = cart.count === 0; });
      cart.items.forEach((it) => {
        const row = cartPage.querySelector(`[data-row="${it.product_id}"]`);
        if (row) { row.querySelector("[data-line]").textContent = fmtINR(it.line_total); row.querySelector("input[name=quantity]").value = it.quantity; }
      });
      if (cart.count === 0) location.reload();
    };
    cartPage.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-qty]");
      const rm = e.target.closest("[data-remove]");
      if (b) {
        e.preventDefault();
        const row = b.closest("[data-row]");
        const input = row.querySelector("input[name=quantity]");
        const qty = Math.max(1, Number(input.value) + Number(b.dataset.qty));
        const data = await post("/cart/update", { product_id: row.dataset.row, quantity: qty });
        if (!data) return;
        if (!data.ok) flash(data.message, "error");
        refresh(data.cart);
      }
      if (rm) {
        e.preventDefault();
        const row = rm.closest("[data-row]");
        const data = await post("/cart/remove", { product_id: row.dataset.row });
        if (!data) return;
        row.remove(); flash("Item removed.", "info"); refresh(data.cart);
      }
    });
    cartPage.addEventListener("change", async (e) => {
      if (e.target.name !== "quantity") return;
      const row = e.target.closest("[data-row]");
      const data = await post("/cart/update", { product_id: row.dataset.row, quantity: e.target.value });
      if (!data) return;
      if (!data.ok) flash(data.message, "error");
      refresh(data.cart);
    });
  }

  // ---- Eco Swap tolerance slider on the product page --------------------------------
  const swapBox = document.querySelector("[data-eco-swap]");
  if (swapBox) {
    const slider = swapBox.querySelector("input[type=range]");
    const label = swapBox.querySelector("[data-tol-label]");
    const list = swapBox.querySelector("[data-swap-list]");
    let timer;
    slider?.addEventListener("input", () => {
      label.textContent = slider.value + "%";
      clearTimeout(timer);
      timer = setTimeout(async () => {
        list.innerHTML = '<div class="skeleton" style="height:90px"></div>';
        const res = await fetch(`/api/eco-swap/${swapBox.dataset.ecoSwap}?tolerance=${slider.value / 100}`);
        const data = await res.json();
        if (!data.alternatives.length) {
          list.innerHTML = `<div class="empty"><div class="icon">🌱</div>No greener alternative within ±${slider.value}% of the price in this category. Try widening the price window.</div>`;
          return;
        }
        list.innerHTML = data.alternatives.map((a) => `
          <div class="card swap-card"><div class="card-body">
            <div class="swap-item">
              <img src="${a.image_url}" alt="">
              <div><div class="n"><a href="/product/${a.product_id}">${a.product_name}</a></div>
              <div class="p">${a.brand || ""} · ${fmtINR(a.price)} · <span class="gain">+${a.score_gain} pts → ${a.eco_score}/100</span></div></div>
            </div>
            <ul class="reasons">${a.reasons.map((r) => `<li>${r}</li>`).join("")}</ul>
          </div></div>`).join("");
      }, 250);
    });
  }

  // ---- dashboard charts (Chart.js, data from /api/dashboard) -------------------------
  const dash = document.querySelector("[data-dashboard]");
  if (dash && window.Chart) {
    const green = ["#1f6f4a", "#3a9d6c", "#8cc9a6", "#c8891a", "#2f5d7c", "#b4423a", "#6b4e2e", "#5e9a2b", "#17695b"];
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.color = "#4a554f";
    fetch("/api/dashboard").then((r) => r.json()).then((d) => {
      new Chart(document.getElementById("chartEco"), {
        type: "bar",
        data: { labels: d.eco_distribution.map((x) => x.band), datasets: [{ label: "Products", data: d.eco_distribution.map((x) => x.count),
          backgroundColor: ["#b4423a", "#d6691e", "#c8891a", "#5e9a2b", "#1f8a4c"], borderRadius: 6 }] },
        options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
      });
      new Chart(document.getElementById("chartCategory"), {
        type: "bar",
        data: { labels: d.category_scores.map((x) => x.category), datasets: [{ label: "Avg Eco-Score", data: d.category_scores.map((x) => x.avg_eco), backgroundColor: "#1f6f4a", borderRadius: 6 }] },
        options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { min: 0, max: 100 } } },
      });
      new Chart(document.getElementById("chartSales"), {
        type: "line",
        data: { labels: d.monthly_sales.map((x) => x.month), datasets: [
          { label: "Revenue (₹)", data: d.monthly_sales.map((x) => x.revenue), borderColor: "#1f6f4a", backgroundColor: "rgba(31,111,74,.12)", fill: true, tension: .3, yAxisID: "y" },
          { label: "Orders", data: d.monthly_sales.map((x) => x.orders), borderColor: "#c8891a", tension: .3, yAxisID: "y1" }] },
        options: { scales: { y: { beginAtZero: true, ticks: { callback: (v) => "₹" + (v / 1000).toFixed(0) + "k" } }, y1: { position: "right", beginAtZero: true, grid: { drawOnChartArea: false }, ticks: { precision: 0 } } } },
      });
      new Chart(document.getElementById("chartCatSales"), {
        type: "doughnut",
        data: { labels: d.category_sales.map((x) => x.category), datasets: [{ data: d.category_sales.map((x) => x.revenue), backgroundColor: green }] },
        options: { plugins: { legend: { position: "right" } }, cutout: "60%" },
      });
      new Chart(document.getElementById("chartPopular"), {
        type: "bar",
        data: { labels: d.popular.map((x) => x.name.length > 28 ? x.name.slice(0, 26) + "…" : x.name), datasets: [{ label: "Units sold", data: d.popular.map((x) => x.units), backgroundColor: "#3a9d6c", borderRadius: 6 }] },
        options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } },
      });
      new Chart(document.getElementById("chartStatus"), {
        type: "doughnut",
        data: { labels: d.statuses.map((x) => x.status), datasets: [{ data: d.statuses.map((x) => x.count), backgroundColor: green }] },
        options: { plugins: { legend: { position: "right" } }, cutout: "60%" },
      });
    }).catch(() => flash("Could not load chart data.", "error"));
  }
})();

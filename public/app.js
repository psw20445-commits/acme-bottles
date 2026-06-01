const state = {
  page: "production",
  meta: { products: [], materials: [], planning_now: "" },
  schedule: null,
  orders: [],
  supplies: [],
};

const api = {
  async get(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },
  async post(path, payload = {}) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed");
    return data;
  },
};

document.addEventListener("DOMContentLoaded", async () => {
  bindNavigation();
  bindModals();
  bindForms();
  document.getElementById("refreshProduction").addEventListener("click", safeLoadAll);
  document.getElementById("orderSearch").addEventListener("input", renderOrders);
  await safeLoadAll();
});

async function loadAll() {
  state.meta = await api.get("/api/meta");
  fillSelect("orderForm", "product_type", state.meta.products);
  fillSelect("supplyForm", "material_type", state.meta.materials);
  const [ordersData, suppliesData, scheduleData] = await Promise.all([
    api.get("/api/purchase-orders"),
    api.get("/api/supplies"),
    api.get("/api/production-status"),
  ]);
  state.orders = ordersData.purchase_orders;
  state.supplies = suppliesData.supply_orders;
  state.schedule = scheduleData;
  document.getElementById("planningDate").textContent = formatLongDate(state.meta.planning_now);
  renderProduction();
  renderOrders();
  renderSupplies(suppliesData.inventory);
}

async function safeLoadAll() {
  try {
    await loadAll();
  } catch (error) {
    toast(`Unable to load dashboard data: ${error.message}`);
  }
}

function bindNavigation() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      state.page = button.dataset.page;
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll(".page").forEach((page) => page.classList.remove("active"));
      document.getElementById(`page-${state.page}`).classList.add("active");
      document.getElementById("breadcrumb").textContent = pageName(state.page);
    });
  });
}

function bindModals() {
  document.querySelectorAll("[data-open-modal]").forEach((button) => {
    button.addEventListener("click", () => openModal(button.dataset.openModal));
  });
  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", () => button.closest(".modal-backdrop").classList.remove("open"));
  });
  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    backdrop.addEventListener("click", (event) => {
      if (event.target === backdrop) backdrop.classList.remove("open");
    });
  });
}

function bindForms() {
  document.getElementById("orderForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const form = event.currentTarget;
      const values = Object.fromEntries(new FormData(form));
      values.quantity = Number(values.quantity);
      await api.post("/api/purchase-orders", values);
      closeModal("orderModal");
      form.reset();
      toast("Purchase order created.");
      await safeLoadAll();
    } catch (error) {
      toast(`Unable to create purchase order: ${error.message}`);
    }
  });

  document.getElementById("supplyForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const form = event.currentTarget;
      const values = Object.fromEntries(new FormData(form));
      values.quantity_kg = Number(values.quantity_kg);
      values.eta = toUtcIso(values.eta);
      await api.post("/api/supplies", values);
      closeModal("supplyModal");
      form.reset();
      toast("Supply order created.");
      await safeLoadAll();
    } catch (error) {
      toast(`Unable to create supply order: ${error.message}`);
    }
  });
}

function renderProduction() {
  const inProduction = document.getElementById("inProduction");
  const activeSlots = state.schedule.in_production.filter(({ order }) => order).length;
  document.getElementById("productionSlots").textContent = `(${activeSlots}/${state.schedule.in_production.length} slots)`;
  inProduction.innerHTML = state.schedule.in_production.map(({ line, order }) => {
    if (!order) {
      return `<article class="line-card"><strong>Idle</strong><div class="line-name">${line}</div><p>No order is currently running on this line.</p></article>`;
    }
    const eta = renderEta(order.expected_completion, state.meta.planning_now, true);
    return `<article class="line-card">
      <strong>${order.po_number}</strong>
      <h3>${escapeHtml(order.customer_name)}</h3>
      <div class="line-name">${line}</div>
      <p>${order.product_type} - ${formatNumber(order.quantity)} units</p>
      <p>ETA: <b class="${eta.isPast ? "late-text" : ""}">${eta.label}</b>${eta.badge}</p>
    </article>`;
  }).join("");

  const rows = state.schedule.orders_fifo.map((order, index) => `
    <tr>
      <td>${index + 1}</td>
      <td class="linkish">${order.po_number}</td>
      <td>${escapeHtml(order.customer_name)}</td>
      <td>${order.product_type}</td>
      <td>${formatNumber(order.quantity)}</td>
      <td>${formatDate(order.order_date)}</td>
      <td>${renderExpectedStart(order)}</td>
      <td>${renderExpectedCompletion(order)}</td>
      <td>${badge(order.status)}</td>
    </tr>
  `);
  document.getElementById("productionTable").innerHTML = rows.join("");
}

function renderOrders() {
  const query = document.getElementById("orderSearch").value.toLowerCase();
  const statusByPo = new Map((state.schedule?.orders_fifo || []).map((order) => [order.po_number, order.status]));
  const filtered = state.orders.filter((order) => {
    const text = `${order.po_number} ${order.customer_name} ${order.product_type}`.toLowerCase();
    return text.includes(query);
  });
  document.getElementById("orderCount").textContent = state.orders.length;
  document.getElementById("ordersTable").innerHTML = filtered.map((order) => `
    <tr>
      <td class="linkish">${order.po_number}</td>
      <td>${escapeHtml(order.customer_name)}</td>
      <td>${order.product_type}</td>
      <td>${formatNumber(order.quantity)}</td>
      <td>${formatDate(order.order_date)}</td>
      <td>${badge(statusByPo.get(order.po_number) || "Pending")}</td>
    </tr>
  `).join("");
}

function renderSupplies(inventory) {
  document.getElementById("inventoryCards").innerHTML = inventory.map((item) => `
    <article class="inventory-card">
      <strong>${item.material_type}</strong>
      <span class="big">${formatNumber(item.on_hand_kg)}</span> kg on hand
      <div class="sub">${formatNumber(item.incoming_kg)} kg incoming - ${item.incoming_count} in transit</div>
    </article>
  `).join("");
  document.getElementById("supplyCount").textContent = `${state.supplies.length} orders`;
  document.getElementById("suppliesTable").innerHTML = state.supplies.map((supply) => {
    const status = new Date(supply.eta) <= new Date(state.meta.planning_now) ? "Received" : "Ordered";
    return `
      <tr>
        <td>${supply.material_type}</td>
        <td>${formatNumber(supply.quantity_kg)} kg</td>
        <td>${displayText(supply.supplier_name)}</td>
        <td>${escapeHtml(supply.tracking_number)}</td>
        <td>${formatDate(supply.order_date)}</td>
        <td>${formatNumericDate(supply.eta)}</td>
        <td>${badge(status)}</td>
      </tr>
    `;
  }).join("");
}

function fillSelect(formId, name, options) {
  const select = document.querySelector(`#${formId} [name="${name}"]`);
  select.innerHTML = options.map((option) => `<option value="${option}">${option}</option>`).join("");
}

function openModal(id) {
  document.getElementById(id).classList.add("open");
}

function closeModal(id) {
  document.getElementById(id).classList.remove("open");
}

function pageName(page) {
  return {
    production: "Production Status",
    orders: "Purchase Orders",
    supplies: "Supplies",
  }[page];
}

function badge(status) {
  const className = status.replaceAll(" ", "");
  return `<span class="badge ${className}">${status}</span>`;
}

function formatDate(value) {
  if (!value) return "&mdash;";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(new Date(value));
}

function formatNumericDate(value) {
  if (!value) return "&mdash;";
  return new Intl.DateTimeFormat("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

function formatLongDate(value) {
  if (!value) return "&mdash;";
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

function formatDateTime(value) {
  if (!value) return "&mdash;";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(new Date(value));
}

function renderExpectedStart(order) {
  if (order.status === "Completed") return "&mdash;";
  if (order.status === "In Production") return `<span class="started-text">Started</span>`;
  return formatDate(order.expected_start);
}

function renderExpectedCompletion(order) {
  if (order.status === "Completed" || !order.expected_completion) return "&mdash;";
  const eta = renderEta(order.expected_completion, state.meta.planning_now, false);
  return `<span class="${eta.isPast ? "late-text" : ""}">${eta.label}${eta.inline}</span>`;
}

function renderEta(value, nowValue, showBadge) {
  if (!value) return { label: "&mdash;", inline: "", badge: "", isPast: false };
  const date = new Date(value);
  const now = new Date(nowValue);
  const diffDays = Math.floor((now - date) / 86400000);
  const isPast = diffDays > 0;
  const label = formatDate(value);
  if (!isPast) return { label, inline: "", badge: "", isPast: false };
  const lateText = `${diffDays}d ${showBadge ? "overdue" : "late"}`;
  return {
    label,
    inline: ` (${lateText})`,
    badge: ` <span class="overdue-pill">${lateText}</span>`,
    isPast: true,
  };
}

function formatNumber(value) {
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function displayText(value) {
  const text = String(value || "").trim();
  return text ? escapeHtml(text) : "&mdash;";
}

function toUtcIso(localDateTime) {
  return new Date(localDateTime).toISOString().replace(".000Z", "Z");
}

function toast(message) {
  const toastElement = document.getElementById("toast");
  toastElement.textContent = message;
  toastElement.classList.add("show");
  setTimeout(() => toastElement.classList.remove("show"), 3500);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

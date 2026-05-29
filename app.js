const callers = [
  {
    id: "priya",
    name: "Priya Sharma",
    first: "Priya",
    initials: "PS",
    status: "Active",
    statusType: "green",
    summary: "Expires in 8 days - Sector 4",
    ringing: true,
    account: "NET-2026-0142",
    phone: "+91 98765 01001",
    plan: "100 Mbps fiber",
    equipment: "TP-Link XZ-000 ONT",
    area: "Sector 4",
    lastFix: "OLT port reboot held for 3 days",
    metrics: {
      planRisk: "Expires in 8 days",
      frustration: "6.8",
      repeated: "ONT red light x3",
      area: "Sector 4 alert",
    },
    history: [
      ["Apr 18", "ONT red LOS light", "Remote reboot fixed issue for 72 hours."],
      ["May 03", "Evening drops", "OLT port J2 showed recurring packet loss."],
      ["May 21", "Same ONT fault", "Field visit recommended if issue returns."],
    ],
  },
  {
    id: "deepika",
    name: "Deepika Rao",
    first: "Deepika",
    initials: "DR",
    status: "Suspended",
    statusType: "orange",
    summary: "Suspended 28 days - Sector 9",
    ringing: false,
    account: "NET-2025-0098",
    phone: "+91 98765 04420",
    plan: "200 Mbps fiber",
    equipment: "Nokia G-010 ONT",
    area: "Sector 9",
    lastFix: "Payment retry link sent",
    metrics: {
      planRisk: "Suspended 28 days",
      frustration: "4.2",
      repeated: "Billing dispute x2",
      area: "Sector 9 stable",
    },
    history: [
      ["Apr 02", "Auto-pay failed", "Card expired; retry link sent to customer."],
      ["Apr 30", "Service suspended", "Non-payment after three reminders."],
      ["May 15", "Reactivation query", "Customer asked about restoring the plan."],
    ],
  },
  {
    id: "vikram",
    name: "Vikram Singh",
    first: "Vikram",
    initials: "VS",
    status: "Active",
    statusType: "green",
    summary: "Expires in 2 days - Sector 2",
    ringing: false,
    account: "NET-2026-0311",
    phone: "+91 98765 07788",
    plan: "300 Mbps fiber",
    equipment: "TP-Link XZ-200 ONT",
    area: "Sector 2",
    lastFix: "Speed profile re-provisioned",
    metrics: {
      planRisk: "Expires in 2 days",
      frustration: "5.5",
      repeated: "Slow speeds x2",
      area: "Sector 2 congestion",
    },
    history: [
      ["Mar 22", "Speed complaint", "Provisioned profile mismatch corrected."],
      ["May 10", "Peak-hour slowdown", "Sector 2 congestion noted on the OLT."],
      ["May 26", "Renewal reminder", "Plan expiring; offered upgrade to 500 Mbps."],
    ],
  },
];

const genericReply =
  "Please restart your router and ONT, check the fiber cable, and wait five minutes. If the issue continues, contact support again so we can create a ticket.";

const genericEvidence = [
  ["No memory", "The agent has no customer history, equipment data, area context, or prior fixes."],
  ["Generic playbook", "Suggested response falls back to restart router, check cables, and wait."],
];

let selected = callers[0];
let memoryOn = true;
let chat = [];

const $ = (id) => document.getElementById(id);

function responseFor(message) {
  if (!memoryOn) return genericReply;

  const text = message.toLowerCase();
  if (selected.status === "Suspended") {
    return `I understand, ${selected.first}. I can see the account is suspended and the last fix was "${selected.lastFix}", so I will not start with router steps. I will send the reactivation link, check the earlier billing dispute, and keep a waiver review ready if payment was already made.`;
  }

  if (text.includes("third") || text.includes("same problem") || text.includes("again")) {
    return `I completely understand, ${selected.first}, and you are right. Your account shows ${selected.metrics.repeated.toLowerCase()} and "${selected.lastFix}" did not hold. I will skip another restart and book a priority field visit with a service credit noted on the ticket.`;
  }

  if (text.includes("red") || text.includes("ont")) {
    return `Thanks, ${selected.first}. That red light matches the recurring fault on your ${selected.equipment}. A remote reboot only held briefly, so I am dispatching a fiber technician to ${selected.area} instead of repeating the same temporary fix.`;
  }

  return `Hi ${selected.first}. I can see your line logged issues in ${selected.area}, and "${selected.lastFix}" only held briefly. Rather than another restart, I am escalating this to a field engineer today and you will get a confirmation SMS within the hour.`;
}

function evidenceFor() {
  if (!memoryOn) return genericEvidence;
  return [
    ["Account history", `${selected.history.length} prior interactions on file, oldest ${selected.history[0][0]}.`],
    ["Equipment data", `${selected.equipment}; last action: ${selected.lastFix.toLowerCase()}.`],
    ["Area context", selected.metrics.area],
    ["Prior fixes", selected.history[selected.history.length - 1][2]],
  ];
}

function renderCallers() {
  $("customer-list").innerHTML = callers
    .map(
      (caller) => `
        <button class="caller ${caller.id === selected.id ? "active" : ""}" type="button" data-customer="${caller.id}">
          <span class="caller-avatar">${caller.initials}</span>
          <span>
            <span class="caller-name">${caller.name}</span>
            <span class="caller-sub">${caller.summary}</span>
          </span>
          ${caller.ringing ? '<span class="caller-dot"></span>' : ""}
        </button>
      `,
    )
    .join("");
}

function setText(id, value) {
  $(id).textContent = value;
}

function renderCustomer() {
  setText("caller-title", selected.name);
  setText("plan-risk", selected.metrics.planRisk);
  setText("repeat-issue", selected.metrics.repeated);
  setText("area-signal", selected.metrics.area);
  setText("customer-name", selected.name);
  setText("account", selected.account);
  setText("phone", selected.phone);
  setText("plan", selected.plan);
  setText("equipment", selected.equipment);
  setText("area", selected.area);
  setText("last-fix", selected.lastFix);
  setText("account-status", selected.status);

  $("account-status").className = `badge ${selected.statusType}`;
  $("status-pill").className = selected.ringing ? "status-pill" : "status-pill idle";
  $("status-pill").innerHTML = `<span class="ring"></span>${selected.ringing ? "Ringing" : "Connected"}`;

  const frustration = Number(selected.metrics.frustration);
  $("frustration").className = `metric-value ${frustration >= 6.5 ? "bad" : frustration >= 5 ? "warn" : ""}`;
  $("frustration").innerHTML = `${selected.metrics.frustration} <span>/ 10</span>`;

  $("ticket-timeline").innerHTML = selected.history
    .map(
      ([date, title, detail]) => `
        <div class="tl-item">
          <div class="tl-top"><span class="tl-date">${date}</span><span class="tl-title">${title}</span></div>
          <div class="tl-detail">${detail}</div>
        </div>
      `,
    )
    .join("");

  renderCallers();
  renderMemoryMode();
  renderGuidance();
  renderChat();
}

function renderMemoryMode() {
  $("memory-toggle").className = memoryOn ? "switch on" : "switch";
  $("memory-state").className = memoryOn ? "mem-state on" : "mem-state";
  $("memory-state").textContent = memoryOn ? "On - full context" : "Off - generic playbook";
  $("context-badge").className = memoryOn ? "badge green" : "badge orange";
  $("context-badge").textContent = memoryOn ? "Full context" : "Low context";

  document.querySelector(".dna-list").style.display = memoryOn ? "" : "none";
  const dna = $("dna-content");
  if (memoryOn) {
    dna.style.display = "";
  } else {
    dna.style.display = "block";
    $("ticket-timeline").innerHTML = `
      <div class="ev-card empty">
        <div class="ev-label">No customer record</div>
        <div class="ev-detail">With memory off, the agent sees only the phone number. No account, equipment, area, or history is available.</div>
      </div>
    `;
  }
}

function renderGuidance() {
  const lastCustomer = [...chat].reverse().find((item) => item.role === "customer");
  const sample = lastCustomer?.text || "Hi, my internet keeps dropping every evening.";
  $("copilot-card").className = memoryOn ? "answer" : "answer generic";
  $("copilot-card").innerHTML = `
    <div class="answer-tag ${memoryOn ? "smart" : "generic"}">
      ${memoryOn ? "Memory-aware response" : "Generic playbook"}
    </div>
    ${responseFor(sample)}
  `;
  $("memory-evidence").innerHTML = evidenceFor()
    .map(
      ([label, detail]) => `
        <div class="ev-card ${memoryOn ? "smart" : label === "No memory" ? "empty" : ""}">
          <div class="ev-label">${label}</div>
          <div class="ev-detail">${detail}</div>
        </div>
      `,
    )
    .join("");
}

function renderChat() {
  if (chat.length === 0) {
    chat = [
      { role: "customer", text: "Hi, my internet keeps dropping every evening." },
      { role: "agent", text: responseFor("Hi, my internet keeps dropping every evening.") },
    ];
  }

  $("chat-log").innerHTML = chat
    .map(
      (item) => `
        <div class="bubble ${item.role}">
          <div class="bubble-who">${item.role === "customer" ? selected.first : "Agent"}</div>
          ${item.text}
        </div>
      `,
    )
    .join("");
  $("chat-log").scrollTop = $("chat-log").scrollHeight;
}

function sendMessage(message) {
  const clean = message.trim();
  if (!clean) return;
  chat.push({ role: "customer", text: clean });
  chat.push({ role: "agent", text: responseFor(clean) });
  renderGuidance();
  renderChat();
}

document.addEventListener("click", (event) => {
  const customerButton = event.target.closest("[data-customer]");
  if (customerButton) {
    selected = callers.find((caller) => caller.id === customerButton.dataset.customer) || callers[0];
    chat = [];
    renderCustomer();
  }

  const scriptButton = event.target.closest("[data-message]");
  if (scriptButton) {
    document.querySelectorAll(".script-btn").forEach((button) => button.classList.remove("active"));
    scriptButton.classList.add("active");
    sendMessage(scriptButton.dataset.message);
  }
});

$("memory-toggle").addEventListener("click", () => {
  memoryOn = !memoryOn;
  chat = [];
  renderCustomer();
});

$("message-form").addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage($("message-input").value);
  $("message-input").value = "";
});

$("reset-chat").addEventListener("click", () => {
  chat = [];
  renderGuidance();
  renderChat();
});

renderCustomer();

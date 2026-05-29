const customers = [
  {
    id: "priya",
    name: "Priya Sharma",
    phone: "+91 98765 01001",
    account: "NET-2026-0142",
    status: "Active",
    statusType: "success",
    plan: "100 Mbps fiber",
    planRisk: "Expires in 8 days",
    equipment: "TP-Link XZ-000 ONT",
    area: "Sector 4",
    frustration: "6.8 / 10",
    repeatIssue: "ONT red light x3",
    areaSignal: "Sector 4 alert",
    lastFix: "OLT port reboot held for 3 days",
    tickets: [
      ["Apr 18", "ONT red LOS light", "Remote reboot fixed issue for 72 hours."],
      ["May 03", "Evening drops", "OLT port J2 showed recurring packet loss."],
      ["May 21", "Same ONT fault", "Field visit recommended if issue returns."],
    ],
    memory: [
      ["Customer bank", "Three similar ONT LOS complaints in six weeks."],
      ["Network bank", "Two nearby Sector 4 customers reported packet loss today."],
      ["Resolution bank", "Temporary reboots worked briefly; field visit is next best action."],
    ],
  },
  {
    id: "deepika",
    name: "Deepika Rao",
    phone: "+91 98765 01002",
    account: "NET-2026-0198",
    status: "Suspended",
    statusType: "danger",
    plan: "50 Mbps fiber",
    planRisk: "Suspended 28 days",
    equipment: "Nokia G-2425G-A router",
    area: "Sector 9",
    frustration: "8.1 / 10",
    repeatIssue: "Billing and speed",
    areaSignal: "No outage",
    lastFix: "Billing waiver restored service last month",
    tickets: [
      ["Apr 02", "Payment not reflected", "Manual reconciliation restored plan."],
      ["Apr 29", "Slow speeds", "Router channel changed after congestion check."],
      ["May 17", "Account suspended", "Customer asked for renewal options."],
    ],
    memory: [
      ["Customer bank", "Deepika had a previous payment reconciliation issue."],
      ["Policy bank", "Suspended users can be offered a payment link and waiver review."],
      ["Resolution bank", "Do not start with router reboot when account status is suspended."],
    ],
  },
  {
    id: "vikram",
    name: "Vikram Singh",
    phone: "+91 98765 01004",
    account: "NET-2026-0221",
    status: "Active",
    statusType: "warning",
    plan: "200 Mbps fiber",
    planRisk: "Expires in 2 days",
    equipment: "Huawei EG8145V5 ONT",
    area: "Sector 2",
    frustration: "4.9 / 10",
    repeatIssue: "Renewal question",
    areaSignal: "Healthy",
    lastFix: "Plan upgrade solved bandwidth complaints",
    tickets: [
      ["Mar 30", "Low upload speed", "Upgraded to 200 Mbps plan."],
      ["Apr 26", "Renewal reminder", "Customer wanted annual plan quote."],
      ["May 24", "Streaming buffering", "No network issue; advised mesh placement."],
    ],
    memory: [
      ["Customer bank", "Vikram prefers annual renewal when discount is clear."],
      ["Network bank", "Sector 2 has normal latency and no incident today."],
      ["Resolution bank", "Mesh placement advice solved the last streaming complaint."],
    ],
  },
];

const genericEvidence = [
  ["No memory", "The agent has no customer history, equipment data, area context, or prior fixes."],
  ["Generic playbook", "Suggested response falls back to restart router, check cables, and wait."],
];

let selectedCustomer = customers[0];
let memoryOn = true;
let chat = [];

const $ = (id) => document.getElementById(id);

function renderCustomerButtons() {
  $("customer-list").innerHTML = customers
    .map(
      (customer) => `
        <button class="customer-button ${customer.id === selectedCustomer.id ? "active" : ""}"
          data-customer="${customer.id}" type="button">
          <strong>${customer.name}</strong>
          <span>${customer.planRisk} | ${customer.area}</span>
        </button>
      `,
    )
    .join("");
}

function setText(id, value) {
  $(id).textContent = value;
}

function renderCustomer() {
  const c = selectedCustomer;
  setText("caller-title", `${c.name} is calling`);
  setText("plan-risk", c.planRisk);
  setText("frustration", c.frustration);
  setText("repeat-issue", c.repeatIssue);
  setText("area-signal", c.areaSignal);
  setText("customer-name", c.name);
  setText("account", c.account);
  setText("phone", c.phone);
  setText("plan", c.plan);
  setText("equipment", c.equipment);
  setText("area", c.area);
  setText("last-fix", c.lastFix);
  setText("account-status", c.status);
  $("account-status").className = `badge ${c.statusType}`;
  $("ticket-timeline").innerHTML = c.tickets
    .map(
      ([date, title, note]) => `
        <div class="ticket">
          <strong>${date} | ${title}</strong>
          <span>${note}</span>
        </div>
      `,
    )
    .join("");
  renderGuidance();
  renderChat();
  renderCustomerButtons();
}

function generateMemoryResponse(message) {
  const c = selectedCustomer;
  if (!memoryOn) {
    return "Please restart your router and ONT, check the fiber cable, and wait five minutes. If the issue continues, contact support again so we can create a ticket.";
  }

  if (c.status === "Suspended") {
    return `${firstName(c.name)}, I can see your account is currently suspended, so I will not waste your time with router steps. I will send the renewal link, check the previous payment reconciliation issue, and keep a waiver review ready if the payment was already made.`;
  }

  if (message.toLowerCase().includes("red") || message.toLowerCase().includes("drop")) {
    return `${firstName(c.name)}, I can see this matches your earlier ${c.repeatIssue} pattern on the ${c.equipment}. The last reboot only held briefly, so I am escalating this to a field visit and OLT port check instead of repeating the same temporary fix.`;
  }

  return `${firstName(c.name)}, I have your ${c.plan}, ${c.equipment}, recent tickets, and area status in front of me. Based on your history, I will skip basic questions and move straight to the next proven fix.`;
}

function renderGuidance() {
  const sample = chat.find((item) => item.role === "customer")?.text || "My internet keeps dropping every evening.";
  $("copilot-card").textContent = generateMemoryResponse(sample);
  $("confidence").textContent = memoryOn ? "93% confidence" : "Low context";
  $("confidence").className = memoryOn ? "badge neutral" : "badge warning";
  $("memory-evidence").innerHTML = (memoryOn ? selectedCustomer.memory : genericEvidence)
    .map(
      ([label, text]) => `
        <div class="evidence">
          <span>${label}</span>
          <p>${text}</p>
        </div>
      `,
    )
    .join("");
}

function renderChat() {
  if (chat.length === 0) {
    chat = [
      { role: "customer", text: "Hi, my internet keeps dropping every evening." },
      { role: "agent", text: generateMemoryResponse("Hi, my internet keeps dropping every evening.") },
    ];
  }

  $("chat-log").innerHTML = chat
    .map((item) => `<div class="message ${item.role}">${item.text}</div>`)
    .join("");
  $("chat-log").scrollTop = $("chat-log").scrollHeight;
}

function firstName(name) {
  return name.split(" ")[0];
}

function sendMessage(message) {
  const clean = message.trim();
  if (!clean) return;
  chat.push({ role: "customer", text: clean });
  chat.push({ role: "agent", text: generateMemoryResponse(clean) });
  renderGuidance();
  renderChat();
}

document.addEventListener("click", (event) => {
  const customerButton = event.target.closest("[data-customer]");
  if (customerButton) {
    selectedCustomer = customers.find((c) => c.id === customerButton.dataset.customer) || customers[0];
    chat = [];
    renderCustomer();
  }

  const scriptButton = event.target.closest("[data-message]");
  if (scriptButton) {
    sendMessage(scriptButton.dataset.message);
  }
});

$("memory-toggle").addEventListener("change", (event) => {
  memoryOn = event.target.checked;
  $("memory-label").textContent = memoryOn ? "Memory on" : "Memory off";
  chat = [];
  renderGuidance();
  renderChat();
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

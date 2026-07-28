const form = document.querySelector("#contact-form");
const submitButton = document.querySelector("#submit-button");
const emptyResult = document.querySelector("#empty-result");
const result = document.querySelector("#result");
const comment = form.elements.comment;
const contactsList = document.querySelector("#contacts-list");
const contactsLoading = document.querySelector("#contacts-loading");
const contactsEmpty = document.querySelector("#contacts-empty");

const examples = {
  name: "Анна Иванова",
  phone: "+7 912 345-67-89",
  email: "anna@example.com",
  comment: "Хочу обсудить разработку backend-сервиса для нового проекта.",
};

function updateCommentCount() {
  document.querySelector("#comment-count").textContent = comment.value.length;
}

function showResult(response, payload) {
  const ok = response.ok;
  const error = payload.error;
  emptyResult.classList.add("hidden");
  result.classList.remove("hidden");
  result.classList.toggle("error", !ok);
  document.querySelector("#result-badge").textContent = `${response.status} ${response.statusText}`;
  document.querySelector("#result-title").textContent = ok ? "Обращение принято" : "Запрос отклонён";
  document.querySelector("#request-id").textContent = payload.request_id || error?.request_id || "—";
  document.querySelector("#category").textContent = payload.category || "—";
  document.querySelector("#message").textContent = payload.message || error?.message || "Неизвестная ошибка";
  document.querySelector("#raw-response").textContent = JSON.stringify(payload, null, 2);
}

function escapeHtml(value) {
  return String(value ?? "—").replace(
    /[&<>"']/g,
    (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    })[character],
  );
}

function statusPill(value) {
  const safe = escapeHtml(value);
  return `<span class="pill ${safe}">${safe}</span>`;
}

function contactCard(contact) {
  const created = new Date(contact.created_at).toLocaleString("ru-RU");
  return `
    <details class="contact-card">
      <summary>
        <span class="contact-person">
          <strong>${escapeHtml(contact.name)}</strong>
          <small>${escapeHtml(contact.email)}</small>
        </span>
        ${statusPill(contact.category)}
        ${statusPill(contact.processing_status)}
        <span class="contact-date">${escapeHtml(created)}</span>
      </summary>
      <div class="contact-details">
        <div class="wide">
          <h3>Комментарий</h3>
          <p>${escapeHtml(contact.comment)}</p>
        </div>
        <div>
          <h3>AI-анализ</h3>
          <div class="ai-grid">
            <div><span>Тональность</span><strong>${escapeHtml(contact.sentiment)}</strong></div>
            <div><span>Срочность</span><strong>${escapeHtml(contact.urgency)}</strong></div>
            <div><span>Провайдер</span><strong>${escapeHtml(contact.ai_provider_status)}</strong></div>
          </div>
          <p>${escapeHtml(contact.ai_summary)}</p>
        </div>
        <div>
          <h3>Контакты и письма</h3>
          <p>${escapeHtml(contact.phone)} · ${escapeHtml(contact.email)}</p>
          <div class="email-statuses">
            <span>Владельцу: ${statusPill(contact.owner_email_status)}</span>
            <span>Пользователю: ${statusPill(contact.user_email_status)}</span>
          </div>
        </div>
      </div>
    </details>`;
}

async function loadContacts() {
  contactsLoading.classList.remove("hidden");
  contactsEmpty.classList.add("hidden");
  try {
    const response = await fetch("/api/contacts");
    if (!response.ok) throw new Error("Contacts unavailable");
    const contacts = await response.json();
    contactsList.innerHTML = contacts.map(contactCard).join("");
    contactsList.classList.toggle("hidden", contacts.length === 0);
    contactsEmpty.classList.toggle("hidden", contacts.length !== 0);
  } catch {
    contactsList.classList.add("hidden");
    contactsEmpty.textContent = "Не удалось загрузить обращения.";
    contactsEmpty.classList.remove("hidden");
  } finally {
    contactsLoading.classList.add("hidden");
  }
}

async function checkHealth() {
  const health = document.querySelector("#health");
  const label = document.querySelector("#health-label");
  try {
    const response = await fetch("/api/health/ready");
    const payload = await response.json();
    health.className = `health ${response.ok ? "ok" : "error"}`;
    label.textContent = response.ok ? "API готов" : `API: ${payload.status || "не готов"}`;
  } catch {
    health.className = "health error";
    label.textContent = "API недоступен";
  }
}

document.querySelector("#fill-example").addEventListener("click", () => {
  Object.entries(examples).forEach(([key, value]) => {
    form.elements[key].value = value;
  });
  updateCommentCount();
});

comment.addEventListener("input", updateCommentCount);
document.querySelector("#refresh-contacts").addEventListener("click", loadContacts);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.firstElementChild.textContent = "Отправляем…";

  try {
    const response = await fetch("/api/contact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    const payload = await response.json();
    showResult(response, payload);
    if (response.ok) await loadContacts();
  } catch {
    showResult(
      { ok: false, status: 0, statusText: "Network Error" },
      { error: { message: "Не удалось соединиться с API" } },
    );
  } finally {
    submitButton.disabled = false;
    submitButton.firstElementChild.textContent = "Отправить обращение";
  }
});

updateCommentCount();
checkHealth();
loadContacts();

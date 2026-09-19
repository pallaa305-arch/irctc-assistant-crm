const API_BASE = '/api';

export async function fetchStats(filter = null) {
  const url = filter ? `${API_BASE}/crm/stats?filter=${filter}` : `${API_BASE}/crm/stats`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed fetching stats');
  return res.json();
}

export async function startBooking(data) {
  const res = await fetch(`${API_BASE}/bookings/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to start booking');
  return json;
}

export async function getBookingState(bookingRef) {
  const res = await fetch(`${API_BASE}/bookings/state/${bookingRef}`);
  if (!res.ok) throw new Error('Failed to get booking state');
  return res.json();
}

export async function sendBookingAction(bookingRef, action, note = null) {
  const res = await fetch(`${API_BASE}/bookings/action/${bookingRef}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, note }),
  });
  if (!res.ok) throw new Error('Failed to dispatch user action');
  return res.json();
}

export async function fetchBookings(params = {}) {
  const query = new URLSearchParams();
  if (params.q) query.append('q', params.q);
  if (params.status && params.status !== 'ALL') query.append('status', params.status);
  if (params.journey_class && params.journey_class !== 'ALL') query.append('journey_class', params.journey_class);
  if (params.limit) query.append('limit', params.limit);
  if (params.offset) query.append('offset', params.offset);

  const res = await fetch(`${API_BASE}/crm/bookings?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch bookings');
  return res.json();
}

export async function updateBookingCRM(id, data) {
  const res = await fetch(`${API_BASE}/crm/bookings/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteBookingCRM(id) {
  const res = await fetch(`${API_BASE}/crm/bookings/${id}`, {
    method: 'DELETE',
  });
  return res.json();
}

export async function fetchPassengers() {
  const res = await fetch(`${API_BASE}/passengers`);
  if (!res.ok) throw new Error('Failed to fetch passengers');
  return res.json();
}

export async function createPassenger(data) {
  const res = await fetch(`${API_BASE}/passengers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create passenger');
  return res.json();
}

export async function updatePassenger(id, data) {
  const res = await fetch(`${API_BASE}/passengers/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deletePassenger(id) {
  const res = await fetch(`${API_BASE}/passengers/${id}`, {
    method: 'DELETE',
  });
  return res.json();
}

export async function fetchJourneys() {
  const res = await fetch(`${API_BASE}/journeys`);
  if (!res.ok) throw new Error('Failed to fetch journeys');
  return res.json();
}

export async function createJourney(data) {
  const res = await fetch(`${API_BASE}/journeys`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to save journey');
  return res.json();
}

export async function deleteJourney(id) {
  const res = await fetch(`${API_BASE}/journeys/${id}`, {
    method: 'DELETE',
  });
  return res.json();
}

export async function fetchSettings() {
  const res = await fetch(`${API_BASE}/settings`);
  return res.json();
}

export async function updateSettings(data) {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function testTelegram() {
  const res = await fetch(`${API_BASE}/settings/test-telegram`, { method: 'POST' });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Telegram test failed');
  return json;
}

export async function testWhatsApp() {
  const res = await fetch(`${API_BASE}/settings/test-whatsapp`, { method: 'POST' });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'WhatsApp test failed');
  return json;
}

export async function deleteAllData() {
  const res = await fetch(`${API_BASE}/settings/delete-all-data`, { method: 'POST' });
  return res.json();
}

export async function fetchLogs(params = {}) {
  const query = new URLSearchParams();
  if (params.level && params.level !== 'ALL') query.append('level', params.level);
  if (params.category && params.category !== 'ALL') query.append('category', params.category);
  const res = await fetch(`${API_BASE}/logs?${query.toString()}`);
  return res.json();
}

export async function fetchSystemStatus() {
  const res = await fetch(`${API_BASE}/system/status`);
  return res.json();
}

export async function triggerBackup() {
  const res = await fetch(`${API_BASE}/crm/backup`, { method: 'POST' });
  return res.json();
}

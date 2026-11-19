const DATABASE_NAME = "speakeasy-local";
const DATABASE_VERSION = 1;
const SESSION_STORE = "sessions";
const USAGE_STORE = "usage";
const RESERVATION_STORE = "reservations";

let databasePromise;

function openDatabase() {
  if (!("indexedDB" in window)) {
    return Promise.reject(new Error("This browser does not support local session history. Use a current version of Chrome, Edge, Firefox or Safari."));
  }
  if (databasePromise) return databasePromise;

  databasePromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(SESSION_STORE)) {
        const sessions = db.createObjectStore(SESSION_STORE, { keyPath: "id" });
        sessions.createIndex("createdAt", "createdAt");
      }
      if (!db.objectStoreNames.contains(USAGE_STORE)) {
        db.createObjectStore(USAGE_STORE, { keyPath: "dateKey" });
      }
      if (!db.objectStoreNames.contains(RESERVATION_STORE)) {
        db.createObjectStore(RESERVATION_STORE, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Unable to open local session history."));
    request.onblocked = () => reject(new Error("Close other SpeakEasy tabs to update local session history."));
  }).catch((error) => {
    databasePromise = null;
    throw error;
  });
  return databasePromise;
}

function transactionComplete(transaction) {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = () => reject(transaction.error || new Error("Local storage transaction was cancelled."));
    transaction.onerror = () => reject(transaction.error || new Error("Local storage transaction failed."));
  });
}

function utcDateKey(timestamp = Date.now()) {
  return new Date(timestamp).toISOString().slice(0, 10);
}

async function releaseExpiredReservations(db, now = Date.now()) {
  const tx = db.transaction([USAGE_STORE, RESERVATION_STORE], "readwrite");
  const done = transactionComplete(tx);
  const usageStore = tx.objectStore(USAGE_STORE);
  const reservationStore = tx.objectStore(RESERVATION_STORE);
  const request = reservationStore.getAll();
  request.onsuccess = () => {
    for (const reservation of request.result || []) {
      if (!reservation.consumed && reservation.expiresAt <= now) {
        const usageRequest = usageStore.get(reservation.dateKey);
        usageRequest.onsuccess = () => {
          const record = usageRequest.result;
          if (record) {
            record.used = Math.max(0, Number(record.used || 0) - 1);
            usageStore.put(record);
          }
        };
        reservationStore.delete(reservation.id);
      }
    }
  };
  await done;
}

export async function getDailyUsage(limit) {
  const db = await openDatabase();
  await releaseExpiredReservations(db);
  const dateKey = utcDateKey();
  const tx = db.transaction(USAGE_STORE, "readonly");
  const done = transactionComplete(tx);
  const request = tx.objectStore(USAGE_STORE).get(dateKey);
  const result = await new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result || { dateKey, used: 0 });
    request.onerror = () => reject(request.error);
  });
  await done;
  return { used: Number(result.used || 0), limit, date: dateKey, scope: "this browser" };
}

export async function reserveDailyUsage(limit, purpose) {
  const db = await openDatabase();
  await releaseExpiredReservations(db);
  const dateKey = utcDateKey();
  const reservationId = crypto.randomUUID();
  const tx = db.transaction([USAGE_STORE, RESERVATION_STORE], "readwrite");
  const done = transactionComplete(tx);
  const usageStore = tx.objectStore(USAGE_STORE);
  const reservationStore = tx.objectStore(RESERVATION_STORE);
  let outcome;
  const request = usageStore.get(dateKey);
  request.onsuccess = () => {
    const usage = request.result || { dateKey, used: 0 };
    if (Number(usage.used || 0) >= limit) {
      outcome = new Error(`Daily practice limit reached (${limit}) on this browser. The allowance resets at 00:00 UTC.`);
      tx.abort();
      return;
    }
    usage.used = Number(usage.used || 0) + 1;
    usageStore.put(usage);
    reservationStore.put({
      id: reservationId,
      dateKey,
      purpose,
      expiresAt: Date.now() + 20 * 60 * 1000,
      consumed: false
    });
    outcome = { reservationId, used: usage.used, limit, date: dateKey };
  };
  try {
    await done;
  } catch (error) {
    throw outcome instanceof Error ? outcome : error;
  }
  return outcome;
}

export async function releaseDailyReservation(reservationId) {
  if (!reservationId) return;
  const db = await openDatabase();
  const tx = db.transaction([USAGE_STORE, RESERVATION_STORE], "readwrite");
  const done = transactionComplete(tx);
  const usageStore = tx.objectStore(USAGE_STORE);
  const reservationStore = tx.objectStore(RESERVATION_STORE);
  const request = reservationStore.get(reservationId);
  request.onsuccess = () => {
    const reservation = request.result;
    if (!reservation) return;
    if (!reservation.consumed) {
      const usageRequest = usageStore.get(reservation.dateKey);
      usageRequest.onsuccess = () => {
        const usage = usageRequest.result;
        if (usage) {
          usage.used = Math.max(0, Number(usage.used || 0) - 1);
          usageStore.put(usage);
        }
      };
    }
    reservationStore.delete(reservationId);
  };
  await done;
}

export async function consumeDailyReservation(reservationId) {
  if (!reservationId) return;
  const db = await openDatabase();
  const tx = db.transaction(RESERVATION_STORE, "readwrite");
  const done = transactionComplete(tx);
  tx.objectStore(RESERVATION_STORE).delete(reservationId);
  await done;
}

export async function saveSession(session) {
  const db = await openDatabase();
  const tx = db.transaction(SESSION_STORE, "readwrite");
  const done = transactionComplete(tx);
  tx.objectStore(SESSION_STORE).put(session);
  await done;
  return session;
}

export async function appendRetry(sessionId, attempt) {
  const db = await openDatabase();
  const tx = db.transaction(SESSION_STORE, "readwrite");
  const done = transactionComplete(tx);
  const store = tx.objectStore(SESSION_STORE);
  let outcome;
  const request = store.get(sessionId);
  request.onsuccess = () => {
    const session = request.result;
    if (!session || session.expiresAt <= Date.now()) {
      outcome = new Error("That practice session is no longer available.");
      tx.abort();
      return;
    }
    if (session.retryUsed || (session.attempts || []).length !== 1) {
      outcome = new Error("The free retry has already been used.");
      tx.abort();
      return;
    }
    session.retryUsed = true;
    session.attempts = [...session.attempts, attempt];
    session.latest = attempt;
    store.put(session);
    outcome = session;
  };
  try {
    await done;
  } catch (error) {
    throw outcome instanceof Error ? outcome : error;
  }
  return outcome;
}

export async function getSession(sessionId) {
  const db = await openDatabase();
  const tx = db.transaction(SESSION_STORE, "readonly");
  const done = transactionComplete(tx);
  const request = tx.objectStore(SESSION_STORE).get(sessionId);
  const result = await new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error);
  });
  await done;
  if (result && result.expiresAt <= Date.now()) {
    await deleteSession(sessionId);
    return null;
  }
  return result;
}

export async function listSessions(limit = 30) {
  const db = await openDatabase();
  const tx = db.transaction(SESSION_STORE, "readwrite");
  const done = transactionComplete(tx);
  const store = tx.objectStore(SESSION_STORE);
  const request = store.getAll();
  const sessions = await new Promise((resolve, reject) => {
    request.onsuccess = () => {
      const now = Date.now();
      const valid = (request.result || []).filter((session) => session.expiresAt > now);
      for (const session of request.result || []) {
        if (session.expiresAt <= now) store.delete(session.id);
      }
      valid.sort((a, b) => b.createdAt - a.createdAt);
      resolve(valid.slice(0, Math.max(1, Math.min(limit, 50))));
    };
    request.onerror = () => reject(request.error);
  });
  await done;
  return sessions;
}

export async function deleteSession(sessionId) {
  const db = await openDatabase();
  const tx = db.transaction(SESSION_STORE, "readwrite");
  const done = transactionComplete(tx);
  tx.objectStore(SESSION_STORE).delete(sessionId);
  await done;
}

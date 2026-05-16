/**
 * UBA API Service Layer
 *
 * Centralised API client with:
 *  - Configurable base URL (VITE_API_URL env var or default)
 *  - Automatic X-User-Role header injection
 *  - Retry logic for transient failures
 *  - Structured error objects
 */

const API_BASE = (import.meta.env.VITE_API_URL || '') + '/api';

// ── Shared fetch wrapper ────────────────────────────────────────────────────

class ApiError extends Error {
    constructor(message, status, endpoint) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.endpoint = endpoint;
    }
}

/**
 * Core fetch wrapper with retry and error handling.
 * @param {string} endpoint  - Path relative to API_BASE (e.g. '/stats')
 * @param {object} options   - Standard fetch options + { retries, role }
 * @returns {Promise<any>}
 */
async function apiFetch(endpoint, options = {}) {
    const { retries = 1, role = null, ...fetchOptions } = options;

    const headers = {
        'Content-Type': 'application/json',
        ...(role ? { 'X-User-Role': role } : {}),
        ...fetchOptions.headers,
    };

    const url = `${API_BASE}${endpoint}`;

    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const response = await fetch(url, { ...fetchOptions, headers });

            if (!response.ok) {
                // Don't retry 4xx errors — they're client bugs, not transient
                if (response.status >= 400 && response.status < 500) {
                    const body = await response.text();
                    throw new ApiError(body || response.statusText, response.status, endpoint);
                }
                // 5xx — retry if attempts remain
                if (attempt < retries) continue;
                throw new ApiError(response.statusText, response.status, endpoint);
            }

            return await response.json();
        } catch (err) {
            if (err instanceof ApiError) throw err;
            // Network error — retry if attempts remain
            if (attempt < retries) continue;
            console.error(`[API] ${endpoint} failed after ${retries + 1} attempts:`, err);
            throw new ApiError(err.message, 0, endpoint);
        }
    }
}

// ── Public API functions ────────────────────────────────────────────────────

/** GET /api/stats — Basic system statistics. */
export const fetchStats = async () => {
    try {
        return await apiFetch('/stats');
    } catch (err) {
        console.error('fetchStats:', err.message);
        return null;
    }
};

/** GET /api/dashboard/summary — Rich dashboard payload (stats + top users + trends). */
export const fetchDashboardSummary = async () => {
    try {
        return await apiFetch('/dashboard/summary');
    } catch (err) {
        console.error('fetchDashboardSummary:', err.message);
        return null;
    }
};

/** GET /api/events/risk — Paginated high-risk events. */
export const fetchRiskyEvents = async (limit = 100, minScore = 0) => {
    try {
        const params = new URLSearchParams({ limit, min_score: minScore });
        return await apiFetch(`/events/risk?${params}`);
    } catch (err) {
        console.error('fetchRiskyEvents:', err.message);
        return { events: [], total: 0 };
    }
};

/** GET /api/users/risk — Sorted risky-user list. */
export const fetchRiskyUsers = async (limit = 50, sort = 'desc') => {
    try {
        const params = new URLSearchParams({ limit, sort });
        return await apiFetch(`/users/risk?${params}`);
    } catch (err) {
        console.error('fetchRiskyUsers:', err.message);
        return [];
    }
};

/** GET /api/users/:id/profile — Single user risk profile. */
export const fetchUserProfile = async (userId) => {
    try {
        return await apiFetch(`/users/${encodeURIComponent(userId)}/profile`);
    } catch (err) {
        console.error('fetchUserProfile:', err.message);
        return null;
    }
};

/** GET /api/users/:id/timeline — Paginated event timeline for a user. */
export const fetchTimeline = async (userId, limit = 100, offset = 0) => {
    try {
        const params = new URLSearchParams({ limit, offset });
        return await apiFetch(`/users/${encodeURIComponent(userId)}/timeline?${params}`);
    } catch (err) {
        console.error('fetchTimeline:', err.message);
        return { events: [], total: 0 };
    }
};

/** GET /api/alerts — Paginated alerts with optional severity/status filters. */
export const fetchAlerts = async ({ limit = 100, offset = 0, severity, status } = {}) => {
    try {
        const params = new URLSearchParams({ limit, offset });
        if (severity) params.set('severity', severity);
        if (status) params.set('status', status);
        return await apiFetch(`/alerts?${params}`);
    } catch (err) {
        console.error('fetchAlerts:', err.message);
        return { alerts: [], total: 0 };
    }
};

/** GET /api/models/status — Status of all trained ML models. */
export const fetchModelStatus = async () => {
    try {
        return await apiFetch('/models/status');
    } catch (err) {
        console.error('fetchModelStatus:', err.message);
        return { models: [] };
    }
};

/** GET /api/analysis/user/:id — Daily risk history for a user (XGBoost-scored). */
export const fetchUserRiskAnalysis = async (userId) => {
    try {
        return await apiFetch(`/analysis/user/${encodeURIComponent(userId)}`);
    } catch (err) {
        console.error('fetchUserRiskAnalysis:', err.message);
        return null;
    }
};

/** GET /api/analysis/explain/:id/:date — SHAP explanation for a user on a date. */
export const fetchRiskExplanation = async (userId, date) => {
    try {
        return await apiFetch(`/analysis/explain/${encodeURIComponent(userId)}/${encodeURIComponent(date)}`);
    } catch (err) {
        console.error('fetchRiskExplanation:', err.message);
        return null;
    }
};

/** POST /api/analysis/feedback — Submit analyst feedback on a risk flag. */
export const submitAnalystFeedback = async ({ userId, day, isFalsePositive, comments = '' }) => {
    try {
        return await apiFetch('/analysis/feedback', {
            method: 'POST',
            body: JSON.stringify({
                user_id: userId,
                day: day,
                is_false_positive: isFalsePositive,
            }),
        });
    } catch (err) {
        console.error('submitAnalystFeedback:', err.message);
        return null;
    }
};

/** POST /api/admin/cache/clear — Clear server-side caches (Admin only). */
export const clearCache = async () => {
  try {
    return await apiFetch('/admin/cache/clear', {
      method: 'POST',
      role: 'Admin',
    });
  } catch (err) {
    console.error('clearCache:', err.message);
    return null;
  }
};

/** GET /api/v1/telemetry/integrity/summary — Get global integrity overview */
export const fetchIntegritySummary = async () => {
  try {
    return await apiFetch('/v1/telemetry/integrity/summary');
  } catch (err) {
    console.error('fetchIntegritySummary:', err.message);
    return null;
  }
};

/** GET /api/v1/telemetry/recent — Get recent telemetry */
export const fetchRecentTelemetry = async (limit = 100) => {
  try {
    const params = new URLSearchParams({ limit });
    return await apiFetch(`/v1/telemetry/recent?${params}`);
  } catch (err) {
    console.error('fetchRecentTelemetry:', err.message);
    return { telemetry: [], count: 0 };
  }
};

/** GET /api/v1/telemetry/user/:userId — Get user telemetry */
export const fetchUserTelemetry = async (userId, limit = 100) => {
  try {
    const params = new URLSearchParams({ limit });
    return await apiFetch(`/v1/telemetry/user/${encodeURIComponent(userId)}?${params}`);
  } catch (err) {
    console.error('fetchUserTelemetry:', err.message);
    return { telemetry: [], count: 0 };
  }
};

/** GET /api/users — List all users */
export const fetchUsers = async (isActive = true) => {
  try {
    const params = new URLSearchParams({ is_active: isActive });
    return await apiFetch(`/users/?${params}`);
  } catch (err) {
    console.error('fetchUsers:', err.message);
    return [];
  }
};

/** GET /api/users/:id — Get single user */
export const fetchUser = async (userId) => {
  try {
    return await apiFetch(`/users/${encodeURIComponent(userId)}`);
  } catch (err) {
    console.error('fetchUser:', err.message);
    return null;
  }
};

/** POST /api/users — Create new user */
export const createUser = async (userData) => {
  try {
    const params = new URLSearchParams(userData);
    return await apiFetch('/users/', {
      method: 'POST',
      body: params.toString(),
    });
  } catch (err) {
    console.error('createUser:', err.message);
    return null;
  }
};

/** PUT /api/users/:id — Update user */
export const updateUser = async (userId, updates) => {
  try {
    return await apiFetch(`/users/${encodeURIComponent(userId)}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  } catch (err) {
    console.error('updateUser:', err.message);
    return null;
  }
};

/** DELETE /api/users/:id — Deactivate user */
export const deleteUser = async (userId) => {
  try {
    return await apiFetch(`/users/${encodeURIComponent(userId)}`, {
      method: 'DELETE',
    });
  } catch (err) {
    console.error('deleteUser:', err.message);
    return null;
  }
};

/** GET /api/users/:id/risk-profile — Get user risk profile */
export const fetchUserRiskProfile = async (userId) => {
  try {
    return await apiFetch(`/users/${encodeURIComponent(userId)}/risk-profile`);
  } catch (err) {
    console.error('fetchUserRiskProfile:', err.message);
    return null;
  }
};

/** GET /api/v1/telemetry/heatmap — Per-user per-hour real risk scores */
export const fetchHeatmapData = async () => {
  return await apiFetch('/v1/telemetry/heatmap');
};

/** GET /api/v1/telemetry/user/:id/hourly — Per-hour activity for one user */
export const fetchUserHourlyActivity = async (userId) => {
  try {
    return await apiFetch(`/v1/telemetry/user/${encodeURIComponent(userId)}/hourly`);
  } catch (err) {
    console.error('fetchUserHourlyActivity:', err.message);
    return { data: [] };
  }
};

// Re-export the error class for consumers that want to catch specifically
export { ApiError };

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from './api';
import type {
  MeResponse,
  CameraSummary,
  CameraEvent,
  AdminUser,
  AuditLogItem,
  SessionItem,
  PrivacyNoticeResponse,
  DeepHealthResponse,
  AdminDashboardResponse,
  AdminGateway,
  DsrRequest,
  BackupStatusResponse,
  BreakGlassStatusResponse,
} from './types';

// ── useMe ──

export function useMe() {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMe = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMe();
      setUser(data);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setUser(null);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load user');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchMe(); }, [fetchMe]);

  return { user, loading, error, refetch: fetchMe };
}

// ── useCameras ──

export function useCameras() {
  const [cameras, setCameras] = useState<CameraSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const fetchCameras = useCallback(async (cursor?: string) => {
    setLoading(true);
    try {
      const data = await api.listCameras(cursor);
      setCameras((prev) => (cursor ? [...prev, ...data.items] : data.items));
      setNextCursor(data.next_cursor);
    } catch {
      // Silently handle — cameras will show empty
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchCameras(); }, [fetchCameras]);

  const loadMore = () => { if (nextCursor) fetchCameras(nextCursor); };

  return { cameras, loading, loadMore, hasMore: !!nextCursor, refetch: () => fetchCameras() };
}

// ── useCameraEvents (SSE) ──

export function useCameraEvents() {
  const [events, setEvents] = useState<CameraEvent[]>([]);
  const [cameraStatuses, setCameraStatuses] = useState<Record<string, string>>({});
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = api.subscribeCameraEvents();
    if (es === null) {
      sourceRef.current = null;
      return;
    }
    sourceRef.current = es;

    es.addEventListener('camera_event', (e) => {
      try {
        const event: CameraEvent = JSON.parse(e.data);
        setEvents((prev) => [event, ...prev].slice(0, 100));
        setCameraStatuses((prev) => ({ ...prev, [event.camera_id]: event.kind }));
      } catch {
        // Invalid SSE data
      }
    });

    es.onerror = () => {
      // SSE will auto-reconnect
    };

    return () => {
      es.close();
      sourceRef.current = null;
    };
  }, []);

  return { events, cameraStatuses };
}

// ── useAdminUsers ──

export function useAdminUsers() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const fetchUsers = useCallback(async (cursor?: string, email?: string) => {
    setLoading(true);
    try {
      const data = await api.listAdminUsers(cursor, 50, email);
      setUsers((prev) => (cursor ? [...prev, ...data.items] : data.items));
      setNextCursor(data.next_cursor);
    } catch {
      // Access denied or error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  return {
    users,
    loading,
    loadMore: () => { if (nextCursor) fetchUsers(nextCursor); },
    hasMore: !!nextCursor,
    refetch: () => fetchUsers(),
  };
}

// ── useAdminAudit ──

export function useAdminAudit(actionFilter?: string) {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const fetchLogs = useCallback(async (cursor?: number) => {
    setLoading(true);
    try {
      const data = await api.listAudit(cursor, 50, actionFilter);
      setLogs((prev) => (cursor ? [...prev, ...data.items] : data.items));
      setNextCursor(data.next_cursor);
    } catch {
      // Access denied or error
    } finally {
      setLoading(false);
    }
  }, [actionFilter]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  return {
    logs,
    loading,
    loadMore: () => {
      if (nextCursor) fetchLogs(Number(nextCursor));
    },
    hasMore: !!nextCursor,
    refetch: () => { setLogs([]); fetchLogs(); },
  };
}

// ── useActiveSessions ──

export function useActiveSessions() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getActiveSessions();
      setSessions(data.items);
    } catch {
      // Error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  return { sessions, loading, refetch: fetchSessions };
}

// ── usePrivacyNotice ──

export function usePrivacyNotice() {
  const [notice, setNotice] = useState<PrivacyNoticeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchNotice = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getPrivacyNotice();
      setNotice(data);
    } catch {
      // Error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchNotice(); }, [fetchNotice]);

  const accept = async () => {
    if (!notice) return;
    await api.acceptPrivacyNotice(notice.notice_version);
    setNotice((n) => n ? { ...n, accepted: true, accepted_at: new Date().toISOString() } : n);
  };

  return { notice, loading, accept, refetch: fetchNotice };
}

// ── useDeepHealth ──

export function useDeepHealth() {
  const [health, setHealth] = useState<DeepHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    api.getDeepHealth()
      .then((data) => { if (mounted) setHealth(data); })
      .catch(() => {})
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  return { health, loading };
}

// ── useSystemHealth (basic /health) ──

export function useSystemHealth() {
  const [status, setStatus] = useState<string>('loading');

  useEffect(() => {
    let mounted = true;
    const check = () => {
      api.getHealth()
        .then((d) => { if (mounted) setStatus(d.status); })
        .catch(() => { if (mounted) setStatus('error'); });
    };
    check();
    const interval = setInterval(check, 30000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  return status;
}

// ── useAdminDashboard ──

export function useAdminDashboard() {
  const [dashboard, setDashboard] = useState<AdminDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getAdminDashboard();
      setDashboard(data);
    } catch {
      // Not admin or error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  return { dashboard, loading, refetch: fetchDashboard };
}

// ── useAdminGateways ──

export function useAdminGateways() {
  const [gateways, setGateways] = useState<AdminGateway[]>([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const fetchGateways = useCallback(async (cursor?: string) => {
    setLoading(true);
    try {
      const data = await api.listAdminGateways(cursor);
      setGateways((prev) => (cursor ? [...prev, ...data.items] : data.items));
      setNextCursor(data.next_cursor);
    } catch {
      // Access denied or error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchGateways(); }, [fetchGateways]);

  return {
    gateways,
    loading,
    loadMore: () => { if (nextCursor) fetchGateways(nextCursor); },
    hasMore: !!nextCursor,
    refetch: () => fetchGateways(),
  };
}

// ── useDsrRequests ──

export function useDsrRequests() {
  const [requests, setRequests] = useState<DsrRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const fetchRequests = useCallback(async (cursor?: string) => {
    setLoading(true);
    try {
      const data = await api.listDsrRequests(cursor);
      setRequests((prev) => (cursor ? [...prev, ...data.items] : data.items));
      setNextCursor(data.next_cursor);
    } catch {
      // Access denied or error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchRequests(); }, [fetchRequests]);

  return {
    requests,
    loading,
    loadMore: () => { if (nextCursor) fetchRequests(nextCursor); },
    hasMore: !!nextCursor,
    refetch: () => fetchRequests(),
  };
}

// ── useBackupStatus ──

export function useBackupStatus() {
  const [backup, setBackup] = useState<BackupStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    api.getBackupStatus()
      .then((data) => { if (mounted) setBackup(data); })
      .catch(() => {})
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  return { backup, loading };
}

// ── useBreakGlassStatus ──

export function useBreakGlassStatus() {
  const [status, setStatus] = useState<BreakGlassStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getBreakGlassStatus();
      setStatus(data);
    } catch {
      // Not admin or error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  return { status, loading, refetch: fetchStatus };
}

import { useState, useCallback } from 'react';
import { Video, Server, Grid2x2, Grid3x3, Square, Command } from 'lucide-react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { StatCard } from './components/StatCard';
import { CameraCard } from './components/CameraCard';
import { CameraDetailModal } from './components/CameraDetailModal';
import { AuditLogTable } from './components/AuditLogTable';
import { AlertsPanel } from './components/AlertsPanel';
import { SystemHealthChart } from './components/SystemHealthChart';
import { UsersSection } from './components/UsersSection';
import { SettingsSection } from './components/SettingsSection';
import { PrivacyNoticeModal } from './components/PrivacyNoticeModal';
import { LoginPage } from './components/LoginPage';
import { CamerasManageSection } from './components/CamerasManageSection';
import { GatewaysSection } from './components/GatewaysSection';
import { HealthSection } from './components/HealthSection';
import { BreakGlassSection } from './components/BreakGlassSection';
import { VisitorInvestigationPage } from './components/VisitorInvestigationPage';
import { ActorInvestigationPage } from './components/ActorInvestigationPage';
import { useMe, useCameras, useCameraEvents, useSystemHealth, usePrivacyNotice, useAdminDashboard } from '../lib/hooks';
import { useTheme } from '../lib/theme';
import type { CameraSummary, CameraTileStatus } from '../lib/types';

type CameraLayout = '1x1' | '2x1' | '2x2';

export function App() {
  const { theme } = useTheme();
  const { user, loading: userLoading, refetch: refetchMe } = useMe();
  const { notice, accept: acceptNotice } = usePrivacyNotice();
  const { cameras, loading: camerasLoading } = useCameras();
  const { events, cameraStatuses } = useCameraEvents();
  const systemStatus = useSystemHealth();
  const { dashboard } = useAdminDashboard();

  const [activeSection, setActiveSection] = useState('dashboard');
  const [selectedCamera, setSelectedCamera] = useState<CameraSummary | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [cameraLayout, setCameraLayout] = useState<CameraLayout>('2x2');

  const handleLogin = useCallback(() => {
    setIsLoggedIn(true);
    refetchMe();
  }, [refetchMe]);

  // ── Auth gate ──
  if (!isLoggedIn && !user && !userLoading) {
    return <LoginPage onLogin={handleLogin} />;
  }

  // ── Loading state ──
  if (userLoading) {
    return (
      <div className={`h-full flex items-center justify-center ${theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className="text-center">
          <img src="/logo.png" alt="Panoptix" className="w-16 h-16 mx-auto rounded-lg mb-4 shadow-xl shadow-orange-500/30 animate-pulse" />
          <p className={theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}>Initializing secure connection...</p>
        </div>
      </div>
    );
  }

  // ── Privacy notice gate ──
  if (notice && !notice.accepted) {
    return <PrivacyNoticeModal title={notice.title} body={notice.body} version={notice.notice_version} onAccept={acceptNotice} />;
  }

  const isAdmin = user?.roles?.includes('admin') ?? false;
  const d = theme === 'dark';

  /**
   * Camera tile status mapping — per ux-product-spec.md and
   * cctv-core-functionality-features.md §3.
   * All 7 states: loading, online, offline, reconnecting, unavailable,
   *   gateway_unavailable, permission_denied
   */
  const getCameraStatus = (cameraId: string): CameraTileStatus => {
    const s = cameraStatuses[cameraId];
    if (s === 'online') return 'online';
    if (s === 'offline') return 'offline';
    if (s === 'reconnecting') return 'reconnecting';
    if (s === 'degraded') return 'unavailable';
    if (s === 'gateway_unavailable') return 'gateway_unavailable';
    if (s === 'permission_denied') return 'permission_denied';
    return 'online';
  };

  // Grid class based on layout — per ux-product-spec.md: 1×1, 2×1, 2×2
  const gridClass = {
    '1x1': 'grid-cols-1 max-w-3xl',
    '2x1': 'grid-cols-1 md:grid-cols-2 max-w-5xl',
    '2x2': 'grid-cols-1 md:grid-cols-2',
  }[cameraLayout];

  const layoutButtons: { layout: CameraLayout; label: string; icon: typeof Square }[] = [
    { layout: '1x1', label: '1×1', icon: Square },
    { layout: '2x1', label: '2×1', icon: Grid2x2 },
    { layout: '2x2', label: '2×2', icon: Grid3x3 },
  ];

  const renderCameraGrid = () => (
    <>
      {/* Layout selector */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h2 className={`text-xl font-bold ${d ? 'text-white' : 'text-slate-900'}`}>Live Camera Feeds</h2>
        <div className="flex items-center gap-1">
          {layoutButtons.map(({ layout, label, icon: Icon }) => (
            <button key={layout} onClick={() => setCameraLayout(layout)} title={`${label} grid`}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm transition-colors ${cameraLayout === layout
                ? 'bg-orange-500/20 text-orange-500 border border-orange-500/30'
                : d ? 'bg-slate-800/50 text-slate-400 hover:text-white' : 'bg-slate-100 text-slate-500 hover:text-slate-900'
              }`}>
              <Icon className="w-4 h-4" /> {label}
            </button>
          ))}
        </div>
      </div>

      {camerasLoading ? (
        <div className={`grid ${gridClass} gap-4`}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className={`aspect-video rounded-lg ${d ? 'bg-slate-800/50 animate-pulse' : 'bg-slate-200 animate-pulse'}`} />
          ))}
        </div>
      ) : cameras.length === 0 ? (
        <div className={`text-center py-16 border rounded-lg ${d ? 'bg-slate-900/50 border-slate-700/50' : 'bg-slate-50 border-slate-200'}`}>
          <Video className={`w-16 h-16 mx-auto mb-4 ${d ? 'text-slate-600' : 'text-slate-300'}`} />
          <h3 className={`text-lg font-semibold mb-2 ${d ? 'text-white' : 'text-slate-900'}`}>No Assigned Cameras</h3>
          <p className={d ? 'text-slate-400' : 'text-slate-500'}>You do not have access to any cameras. Contact your administrator to get camera access.</p>
        </div>
      ) : (
        <div className={`grid ${gridClass} gap-4`}>
          {cameras.map(camera => (
            <CameraCard key={camera.camera_id} id={camera.camera_id} name={camera.display_name}
              location={camera.livekit_room_name} status={getCameraStatus(camera.camera_id)}
              onExpand={() => setSelectedCamera(camera)}
              viewerEmail={user?.email}
            />
          ))}
        </div>
      )}
    </>
  );

  // Use real dashboard data when available, fall back to local state
  const dashCameras = dashboard?.cameras?.active ?? cameras.length;
  const dashGateways = dashboard?.gateways?.enabled ?? 0;
  const dashCmdPending = dashboard?.commands?.pending ?? 0;

  const renderContent = () => {
    switch (activeSection) {
      case 'dashboard':
        return (
          <div className="space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              <StatCard title="Active Cameras" value={dashCameras} icon={Video} color="orange" change={dashboard ? `${dashboard.cameras.total} total` : undefined} />
              <StatCard title="System Status" value={systemStatus === 'ok' ? 'Operational' : 'Checking'} icon={Server} color="emerald" />
              <StatCard title="Gateways Online" value={dashGateways} icon={Server} color="blue" change={dashboard ? `${dashboard.gateways.total} total` : undefined} />
              <StatCard title="Pending Commands" value={dashCmdPending} icon={Command} color={dashCmdPending > 0 ? 'amber' : 'emerald'} />
            </div>
            {renderCameraGrid()}
            <SystemHealthChart />
          </div>
        );

      case 'cameras':
        return <div className="space-y-6">{renderCameraGrid()}</div>;

      case 'manage-cameras':
        return <CamerasManageSection />;

      case 'gateways':
        return <GatewaysSection />;

      case 'users':
        return <UsersSection />;

      case 'audit':
        return <AuditLogTable />;

      case 'alerts':
        return (
          <div className="space-y-6">
            <div>
              <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-white' : 'text-slate-900'}`}>Alerts & Notifications</h2>
              <p className={d ? 'text-slate-400' : 'text-slate-500'}>Security events, system warnings, and operational alerts</p>
            </div>
            <AlertsPanel />
          </div>
        );

      case 'visitors':
        return (
          <div className="space-y-6">
            <div>
              <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-white' : 'text-slate-900'}`}>Visitor Investigation</h2>
              <p className={d ? 'text-slate-400' : 'text-slate-500'}>Public entry visit records and browser/network/risk context</p>
            </div>
            <VisitorInvestigationPage />
          </div>
        );

      case 'actors':
        return (
          <div className="space-y-6">
            <div>
              <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-white' : 'text-slate-900'}`}>Actor Investigation</h2>
              <p className={d ? 'text-slate-400' : 'text-slate-500'}>Profile and activity timeline for users, gateways, and system actors</p>
            </div>
            <ActorInvestigationPage />
          </div>
        );

      case 'health':
        return <HealthSection />;

      case 'break-glass':
        return <BreakGlassSection />;

      case 'settings':
        return <SettingsSection user={user} />;

      default:
        return null;
    }
  };

  return (
    <div className={`h-full flex ${d ? 'bg-slate-950' : 'bg-slate-50'}`}>
      <Sidebar activeSection={activeSection} onSectionChange={setActiveSection} isAdmin={isAdmin} systemStatus={systemStatus} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header user={user} alertCount={events.length} />
        <main className="flex-1 overflow-auto p-6">{renderContent()}</main>
      </div>
      {selectedCamera && <CameraDetailModal camera={selectedCamera} onClose={() => setSelectedCamera(null)} />}
    </div>
  );
}

// src/components/Layout.tsx
import { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';
import {
  Activity, LayoutDashboard, Monitor, Cpu, Bell,
  FlaskConical, BrainCircuit, ShieldCheck, Settings, LogOut,
  ChevronLeft, Sun, Moon, Globe, Wifi, WifiOff, RefreshCw
} from 'lucide-react';

type LiveState = 'live' | 'offline';

const NAV = [
  { to: '/',          label: 'Overview',     icon: LayoutDashboard,  roles: ['admin','doctor','auditor'] },
  { to: '/monitor',   label: 'Live Monitor', icon: Monitor,          roles: ['admin','doctor','auditor'] },
  { to: '/devices',   label: 'Devices',      icon: Cpu,              roles: ['admin','doctor','auditor'] },
  { to: '/alerts',    label: 'Alerts',       icon: Bell,             roles: ['admin','doctor','auditor'] },
  { to: '/decisionlab',label: 'Decision Lab',icon: FlaskConical,     roles: ['admin','doctor','auditor'] },
  { to: '/model',     label: 'Model & Data', icon: BrainCircuit,     roles: ['admin','doctor','auditor'] },
  { to: '/audit',     label: 'Audit',        icon: ShieldCheck,      roles: ['admin','auditor']         },
  { to: '/system',    label: 'System',       icon: Settings,         roles: ['admin','auditor']         },
  { to: '/admin',     label: 'Admin',        icon: Activity,         roles: ['admin']                   },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark');
  const [apiStatus, setApiStatus] = useState<LiveState>('offline');

  // Apply dark theme
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('theme', dark ? 'dark' : 'light');
  }, [dark]);

  // Poll API health every 10s
  useEffect(() => {
    const check = () =>
      api.health()
        .then(() => setApiStatus('live'))
        .catch(() => setApiStatus('offline'));
    check();
    const id = setInterval(check, 10_000);
    return () => clearInterval(id);
  }, []);

  const visibleNav = NAV.filter(n => !user || n.roles.includes(user.role));

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--page)', color: 'var(--text)' }}>

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside
        className="flex flex-col transition-all duration-200 border-r shrink-0"
        style={{
          width: collapsed ? 56 : 240,
          background: 'var(--surface)',
          borderColor: 'var(--border)',
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          {!collapsed && (
            <span className="font-bold text-sm leading-tight" style={{ color: 'var(--text)' }}>
              Telemedicine<br />
              <span style={{ color: 'var(--cloud)' }}>Operations Portal</span>
            </span>
          )}
          <button
            onClick={() => setCollapsed(c => !c)}
            className="ml-auto rounded p-1 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <ChevronLeft
              size={16}
              className="transition-transform"
              style={{ transform: collapsed ? 'rotate(180deg)' : 'none' }}
            />
          </button>
        </div>

        {/* Nav links */}
        <nav className="flex-1 overflow-y-auto py-2">
          {visibleNav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 mx-2 my-0.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'text-white'
                    : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                }`
              }
              style={({ isActive }) => isActive ? { background: 'var(--cloud)' } : { color: 'var(--muted)' }}
              title={collapsed ? label : undefined}
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed && label}
            </NavLink>
          ))}
        </nav>

        {/* User block */}
        {user && (
          <div className="border-t p-3" style={{ borderColor: 'var(--border)' }}>
            {!collapsed && (
              <div className="text-xs mb-2" style={{ color: 'var(--muted)' }}>
                <div className="font-semibold" style={{ color: 'var(--text)' }}>{user.username}</div>
                <div className="capitalize">{user.role}</div>
              </div>
            )}
            <button
              onClick={() => { logout(); navigate('/login'); }}
              className="flex items-center gap-2 text-xs w-full rounded-lg px-2 py-1.5 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
              style={{ color: 'var(--emergency)' }}
            >
              <LogOut size={14} />
              {!collapsed && 'Sign out'}
            </button>
          </div>
        )}
      </aside>

      {/* ── Main area ───────────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0">

        {/* Top bar */}
        <header
          className="flex items-center gap-4 px-6 py-3 border-b shrink-0"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
        >
          {/* Live status pill */}
          <div className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full"
            style={{
              background: apiStatus === 'live' ? 'rgba(21,128,61,0.12)' : 'rgba(220,38,38,0.10)',
              color: apiStatus === 'live' ? 'var(--ok)' : 'var(--emergency)',
            }}>
            {apiStatus === 'live'
              ? <><Wifi size={12} /> Live</>
              : <><WifiOff size={12} /> Offline</>}
          </div>

          <div className="flex items-center gap-1 text-xs ml-1" style={{ color: 'var(--muted)' }}>
            <Globe size={12} />
            <span>Asia/Kolkata (IST)</span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => window.location.reload()}
              className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
              aria-label="Refresh"
              title="Refresh"
            >
              <RefreshCw size={15} style={{ color: 'var(--muted)' }} />
            </button>
            <button
              onClick={() => setDark(d => !d)}
              className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
              aria-label="Toggle theme"
              title="Toggle light/dark"
            >
              {dark ? <Sun size={15} /> : <Moon size={15} />}
            </button>
            {user && (
              <span className="text-xs px-3 py-1 rounded-full font-medium capitalize"
                style={{ background: 'rgba(37,99,235,0.1)', color: 'var(--cloud)' }}>
                {user.role}
              </span>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6 max-w-[1440px] w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

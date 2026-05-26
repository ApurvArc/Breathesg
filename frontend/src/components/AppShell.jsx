import { useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  CircleHelp,
  Database,
  History,
  Leaf,
  LogOut,
  Plus,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  UploadCloud,
} from 'lucide-react';
import { useAppContext } from '../context/AuthContext';
import { loadReadNotificationIds, saveReadNotificationIds } from '../utils/preferences';

const navItems = [
  { to: '/dashboard', label: 'Data Sources', icon: Database },
  { to: '/ingest', label: 'Data Ingestion', icon: UploadCloud },
  { to: '/review', label: 'Analyst Review', icon: SlidersHorizontal },
  { to: '/ledger', label: 'Carbon Ledger', icon: ShieldCheck },
  { to: '/audit', label: 'Audit Log', icon: History },
];

const pageMeta = {
  '/dashboard': ['Data Sources Overview', 'Enterprise data clusters', 'Search ingestions...'],
  '/ingest': ['Ingestion Wizard', 'SAP, Utility, and Travel CSV', 'Search parameters...'],
  '/review': ['Normalization Review', 'Analyst validation queue', 'Search normalized data...'],
  '/ledger': ['Carbon Ledger', 'Append-only audit inventory', 'Search ledger entries...'],
  '/audit': ['Audit Log', 'Immutable event history', 'Search audit trails...'],
  '/settings': ['Settings', 'Workspace preferences', 'Search settings...'],
};

const AppShell = ({ children, path, reviewCount = 0 }) => {
  const { user, logout } = useAppContext();
  const navigate = useNavigate();
  const notificationRef = useRef(null);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [readIds, setReadIds] = useState(() => loadReadNotificationIds());
  const [title, context, search] = pageMeta[path] || pageMeta['/dashboard'];
  const displayName = user?.full_name || user?.username;
  const initials = displayName
    ? displayName.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()
    : user?.username?.slice(0, 2).toUpperCase() || 'AE';

  useEffect(() => {
    if (!notificationsOpen) return undefined;
    const closeOutside = (event) => {
      if (!notificationRef.current?.contains(event.target)) setNotificationsOpen(false);
    };
    const closeWithEscape = (event) => {
      if (event.key === 'Escape') setNotificationsOpen(false);
    };
    document.addEventListener('mousedown', closeOutside);
    document.addEventListener('keydown', closeWithEscape);
    return () => {
      document.removeEventListener('mousedown', closeOutside);
      document.removeEventListener('keydown', closeWithEscape);
    };
  }, [notificationsOpen]);

  const notifications = useMemo(() => [
    reviewCount > 0 && {
      id: `review-${reviewCount}`,
      title: `${reviewCount} records need review`,
      text: 'Pending or flagged rows are waiting for analyst validation.',
      to: '/review',
      icon: AlertTriangle,
      tone: 'text-status-critical bg-error-container',
    },
    {
      id: 'ingestion-ready',
      title: 'Ingestion gateway ready',
      text: 'SAP, utility, and travel sources can be uploaded now.',
      to: '/ingest',
      icon: CheckCircle2,
      tone: 'text-status-verified bg-status-verified/10',
    },
    {
      id: 'audit-enabled',
      title: 'Audit ledger enabled',
      text: 'Approved records remain traceable in the carbon ledger.',
      to: '/ledger',
      icon: ShieldCheck,
      tone: 'text-secondary bg-secondary-container',
    },
  ].filter(Boolean), [reviewCount]);
  const unreadCount = notifications.filter((notification) => !readIds.has(notification.id)).length;

  const markRead = (id) => {
    setReadIds((previous) => {
      const next = new Set(previous);
      next.add(id);
      saveReadNotificationIds(next);
      return next;
    });
  };

  const markAllRead = () => {
    const next = new Set([...readIds, ...notifications.map((notification) => notification.id)]);
    saveReadNotificationIds(next);
    setReadIds(next);
  };

  const openNotification = (notification) => {
    markRead(notification.id);
    setNotificationsOpen(false);
    navigate(notification.to);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-background text-on-surface font-body-md overflow-x-hidden">
      <aside className="fixed left-0 top-0 h-screen w-64 bg-background border-r border-outline-variant flex flex-col pt-10 pb-6 z-50 max-md:static max-md:w-full max-md:h-auto max-md:border-r-0 max-md:border-b max-md:py-4">
        <div className="mb-10 flex items-center gap-3 max-md:mb-4 px-6">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-primary-container text-on-primary">
            <Leaf size={20} fill="currentColor" />
          </div>
          <div className="min-w-0">
            <strong className="block font-headline-sm text-xl leading-none font-extrabold text-primary truncate">Breathe ESG</strong>
            <span className="mt-1 block font-label-mono text-[10px] font-semibold tracking-[0.06em] text-on-surface-variant opacity-70 truncate">Enterprise Audit</span>
          </div>
        </div>

        <nav className="flex-1 space-y-1 max-md:flex max-md:space-y-0 max-md:overflow-x-auto max-md:pb-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => [
                  'flex items-center px-6 py-3 transition-colors max-md:min-w-[160px] max-md:min-h-12 max-md:border-r-0 max-md:border-b-4',
                  isActive 
                    ? 'text-primary font-bold border-r-4 border-primary bg-surface-container-high/30' 
                    : 'text-on-surface-variant font-medium hover:bg-surface-container-high/50 border-r-4 border-transparent'
                ].join(' ')}
              >
                <Icon size={20} className="mr-3" />
                <span className="text-label-mono font-label-mono">{item.label}</span>
                {item.to === '/review' && reviewCount > 0 && (
                  <em className="ml-auto grid h-5 min-w-5 place-items-center rounded-full bg-error-container px-1.5 text-[10px] not-italic text-status-critical">
                    {reviewCount > 99 ? '99+' : reviewCount}
                  </em>
                )}
              </NavLink>
            );
          })}
        </nav>

        <div className="mt-auto px-6 mb-8 max-md:hidden">
          <button
            className="cursor-pointer w-full bg-primary text-on-primary py-3 px-4 rounded-lg font-bold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity"
            onClick={() => navigate('/ingest')}
          >
            <Plus size={16} />
            <span className="text-label-mono">New Ingestion</span>
          </button>
        </div>

        <div className="border-t border-outline-variant pt-4 space-y-1 max-md:hidden">
          <NavLink
            to="/settings"
            className={({ isActive }) => [
              'flex items-center px-6 py-2 transition-colors',
              isActive 
                ? 'text-primary font-bold bg-surface-container-high/30' 
                : 'text-on-surface-variant font-medium hover:bg-surface-container-high/50'
            ].join(' ')}
          >
            <Settings size={20} className="mr-3" />
            <span className="text-label-mono font-label-mono">Settings</span>
          </NavLink>
          <a className="flex items-center px-6 py-2 text-on-surface-variant font-medium hover:bg-surface-container-high/50 transition-colors" href="mailto:support@breathesg.example">
            <CircleHelp size={20} className="mr-3" />
            <span className="text-label-mono font-label-mono">Support</span>
          </a>
          <button className="flex w-full items-center px-6 py-2 text-on-surface-variant font-medium hover:bg-surface-container-high/50 transition-colors text-left bg-transparent border-0 cursor-pointer" onClick={handleLogout}>
            <LogOut size={20} className="mr-3" />
            <span className="text-label-mono font-label-mono">Log Out</span>
          </button>
        </div>
      </aside>

      <div className="ml-64 min-h-screen max-md:ml-0">
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between gap-6 border-b border-outline-variant bg-surface px-6 max-md:static max-md:px-4 max-md:py-4">
          <div className="flex items-center">
            <h2 className="text-headline-sm font-headline-sm text-xl text-primary m-0 font-bold">{title}</h2>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-4 text-on-surface-variant">
              <div className="relative" ref={notificationRef}>
                <button
                  aria-label="Notifications"
                  aria-expanded={notificationsOpen}
                  className="cursor-pointer hover:text-primary transition-colors duration-75 active:scale-95 flex items-center justify-center relative"
                  onClick={() => setNotificationsOpen((open) => !open)}
                >
                  <Bell size={24} />
                  {unreadCount > 0 && <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-status-critical px-1 font-label-mono text-[9px] font-bold text-on-error">{unreadCount}</span>}
                </button>
                {notificationsOpen && (
                  <section className="absolute right-0 top-10 z-50 w-[390px] overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest shadow-[0_18px_45px_rgba(25,28,24,0.16)] max-sm:fixed max-sm:left-4 max-sm:right-4 max-sm:top-28 max-sm:w-auto">
                    <header className="flex items-center justify-between border-b border-outline-variant px-5 py-4">
                      <div>
                        <h2 className="m-0 font-headline-sm text-lg font-bold text-primary">Notifications</h2>
                        <span className="text-xs text-on-surface-variant">{unreadCount} unread alert{unreadCount === 1 ? '' : 's'}</span>
                      </div>
                      <button className="cursor-pointer border-0 bg-transparent font-label-mono text-xs font-bold text-secondary" onClick={markAllRead}>Mark all read</button>
                    </header>
                    <div className="grid">
                      {notifications.map((notification) => {
                        const Icon = notification.icon;
                        const unread = !readIds.has(notification.id);
                        return (
                          <button
                            className="cursor-pointer flex gap-3 border-0 border-b border-outline-variant bg-surface-container-lowest px-5 py-4 text-left transition hover:bg-surface-container-low"
                            key={notification.id}
                            onClick={() => openNotification(notification)}
                          >
                            <span className={`mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg ${notification.tone}`}><Icon size={18} /></span>
                            <span className="min-w-0 flex-1">
                              <strong className="block text-sm">{notification.title}</strong>
                              <span className="mt-1 block text-sm leading-snug text-on-surface-variant">{notification.text}</span>
                            </span>
                            {unread && <span className="mt-2 h-2.5 w-2.5 rounded-full bg-secondary" />}
                          </button>
                        );
                      })}
                    </div>
                    <button className="cursor-pointer w-full border-0 bg-surface-container-low px-5 py-3 text-left font-label-mono text-xs font-bold uppercase tracking-[0.05em] text-primary transition hover:bg-surface-container" onClick={() => { setNotificationsOpen(false); navigate('/settings'); }}>View Profile</button>
                  </section>
                )}
              </div>
              <button aria-label="Support and preferences" className="cursor-pointer hover:text-primary transition-colors duration-75 active:scale-95 flex items-center justify-center" onClick={() => navigate('/settings')}><CircleHelp size={20} /></button>
              <div className="h-8 w-8 rounded-full bg-tertiary-fixed flex items-center justify-center overflow-hidden border border-outline-variant cursor-pointer text-xs font-extrabold text-on-tertiary-fixed" onClick={() => navigate('/settings')}>
                {initials}
              </div>
              <button className="cursor-pointer hover:text-primary transition-colors duration-75 active:scale-95 flex items-center justify-center max-md:hidden" onClick={handleLogout}><LogOut size={20} /></button>
            </div>
          </div>
        </header>
        <main className="p-8 max-w-[1440px] mx-auto max-lg:p-6 max-md:p-4">{children}</main>
      </div>
    </div>
  );
};

export default AppShell;

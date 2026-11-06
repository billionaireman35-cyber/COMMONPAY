import { useState } from "react";
import CloseTheDay from "./features/close/CloseTheDay";
import Payouts from "./features/payouts/Payouts";
import BusinessSummary from "./features/overview/BusinessSummary";
import Reconciliation from "./features/core/Reconciliation";
import Checkout from "./features/core/Checkout";
import Intelligence from "./features/core/Intelligence";
import Developers from "./features/core/Developers";
import Transfers from "./features/core/Transfers";
import {
  Activity,
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  Bell,
  BrainCircuit,
  Building2,
  ChevronDown,
  CircleHelp,
  Command,
  CreditCard,
  LayoutDashboard,
  Lock,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Wallet,
  X,
} from "lucide-react";

const personalNav = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Accounts", icon: Wallet },
  { label: "Payments", icon: ArrowUpRight },
  { label: "Transfers", icon: ArrowLeftRight },
  { label: "Exchange", icon: Activity },
  { label: "Intelligence", icon: BrainCircuit },
];

const businessNav = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Close the day", icon: Lock },
  { label: "Salary payouts", icon: Send },
  { label: "Payments", icon: ArrowUpRight },
  { label: "Reconciliation", icon: ShieldCheck },
  { label: "Treasury", icon: Building2 },
  { label: "Developers", icon: Command },
];

function App() {
  const [active, setActive] = useState("Overview");
  const [environment, setEnvironment] = useState("Personal");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const nav = environment === "Business" ? businessNav : personalNav;

  function switchEnvironment() {
    setEnvironment(environment === "Personal" ? "Business" : "Personal");
    setActive("Overview");
  }

  return (
    <div className={`app-shell ${collapsed ? "is-collapsed" : ""}`}>
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">C</div>
          <div>
            <strong>commonpay</strong>
            <span>FINANCIAL COMMAND CENTRE</span>
          </div>
          <button className="mobile-close" onClick={() => setMobileOpen(false)}>
            <X size={19} />
          </button>
        </div>

        <div className="environment-switch">
          <span>WORKSPACE</span>
          <button onClick={switchEnvironment}>
            {environment === "Personal" ? <Wallet size={17} /> : <Building2 size={17} />}
            {environment}
            <ChevronDown size={15} />
          </button>
        </div>

        <div className="nav-label">YOUR FINANCES</div>
        <nav>
          {nav.map(({ label, icon: Icon }) => (
            <button
              key={label}
              className={`nav-item ${active === label ? "active" : ""}`}
              onClick={() => {
                setActive(label);
                setMobileOpen(false);
              }}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button className="nav-item">
            <Settings size={18} /><span>Settings</span>
          </button>
          <button className="nav-item">
            <CircleHelp size={18} /><span>Help & support</span>
          </button>
          <div className="profile-card">
            <div className="avatar">G</div>
            <div>
              <strong>Goldx Technologies</strong>
              <span>Workspace owner</span>
            </div>
            <ChevronDown size={15} />
          </div>
        </div>
      </aside>

      {mobileOpen && (
        <button
          className="mobile-overlay"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        />
      )}

      <main className="main-area">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileOpen(true)}>
            <Menu size={21} />
          </button>
          <button className="collapse-btn" onClick={() => setCollapsed(!collapsed)} aria-label="Toggle sidebar">
            {collapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}
          </button>
          <div className="breadcrumb">
            <span>CommonPay</span><span>/</span><strong>{active}</strong>
          </div>
          <div className="top-actions">
            <button className="icon-button" aria-label="Search">
              <Search size={19} />
            </button>
            <button className="icon-button" aria-label="Notifications">
              <Bell size={19} />
            </button>
            <div className="top-avatar">G</div>
          </div>
        </header>

        <div className="page-content">
          {active === "Close the day" ? (
            <CloseTheDay />
          ) : active === "Salary payouts" ? (
            <Payouts />
          ) : active === "Payments" ? (
            <Checkout />
          ) : active === "Reconciliation" ? (
            <Reconciliation />
          ) : active === "Intelligence" ? (
            <Intelligence />
          ) : active === "Developers" ? (
            <Developers />
          ) : active === "Transfers" ? (
            <Transfers />
          ) : active === "Overview" ? (
            <>
              <section className="welcome-row">
                <div>
                  <div className="eyebrow">{environment === "Business" ? "BUSINESS OVERVIEW" : "FINANCIAL OVERVIEW"}</div>
                  <h1>{environment === "Business" ? "Your business command centre." : "Your financial command centre."}</h1>
                  <p>{environment === "Business" ? "Your sales, confirmations and settlements in one view." : "One clear view of your financial world."}</p>
                </div>
                <button className="primary-button">
                  <Plus size={17} /> Add account
                </button>
              </section>

              <section className="status-banner">
                <div className="status-icon"><ShieldCheck size={20} /></div>
                <div>
                  <strong>Your workspace is ready to connect.</strong>
                  <p>Connect an approved financial account to begin seeing your financial position.</p>
                </div>
                <span className="environment-tag">SETUP</span>
              </section>

              {environment === "Business" ? (
                <BusinessSummary />
              ) : (
              <section className="summary-grid">
                <article className="summary-card">
                  <div className="card-heading">
                    <span>{environment === "Business" ? "Sales today" : "Total balance"}</span><Wallet size={18} />
                  </div>
                  <div className="empty-value">—</div>
                  <p>No financial accounts connected</p>
                </article>
                <article className="summary-card">
                  <div className="card-heading">
                    <span>{environment === "Business" ? "Confirmed" : "Money received"}</span><ArrowDownLeft size={18} />
                  </div>
                  <div className="empty-value">—</div>
                  <p>Transaction history will appear here</p>
                </article>
                <article className="summary-card">
                  <div className="card-heading">
                    <span>{environment === "Business" ? "Still pending" : "Money sent"}</span><ArrowUpRight size={18} />
                  </div>
                  <div className="empty-value">—</div>
                  <p>Transaction history will appear here</p>
                </article>
              </section>
              )}

              <section className="content-grid">
                <article className="panel activity-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Recent activity</h2>
                      <p>Your latest financial movements</p>
                    </div>
                    <button className="text-button">View all</button>
                  </div>
                  <div className="empty-state">
                    <div className="empty-icon"><CreditCard size={23} /></div>
                    <strong>No transactions yet</strong>
                    <p>Your activity will appear here once an account is connected.</p>
                  </div>
                </article>

                <article className="panel quick-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Quick actions</h2>
                      <p>Common financial tasks</p>
                    </div>
                  </div>
                  <button className="quick-action" onClick={() => setActive("Payments")}>
                    <span className="quick-icon"><ArrowUpRight size={18} /></span>
                    <span><strong>Make a payment</strong><small>Pay a person or business</small></span>
                  </button>
                  <button className="quick-action" onClick={() => setActive("Transfers")}>
                    <span className="quick-icon"><ArrowLeftRight size={18} /></span>
                    <span><strong>Transfer money</strong><small>Move money between accounts</small></span>
                  </button>
                  <button className="quick-action" onClick={() => setActive("Intelligence")}>
                    <span className="quick-icon"><BrainCircuit size={18} /></span>
                    <span><strong>Ask CommonPay AI</strong><small>Understand your finances</small></span>
                  </button>
                </article>
              </section>

              <section className="panel intelligence-panel">
                <div className="ai-symbol"><BrainCircuit size={23} /></div>
                <div>
                  <div className="eyebrow">COMMONPAY INTELLIGENCE</div>
                  <h2>Financial clarity, with intelligence.</h2>
                  <p>Your financial assistant will help explain activity, identify patterns and prepare authorised workflows.</p>
                </div>
                <button className="secondary-button" onClick={() => setActive("Intelligence")}>
                  Explore intelligence
                </button>
              </section>
            </>
          ) : (
            <section className="section-placeholder">
              <div className="placeholder-icon">
                {active === "Intelligence" ? <BrainCircuit size={28} /> : <Command size={28} />}
              </div>
              <div className="eyebrow">COMMONPAY / {active.toUpperCase()}</div>
              <h1>{active}</h1>
              <p>
                This workspace is being prepared. Connect the required financial
                infrastructure and complete the relevant approvals before
                activating live services.
              </p>
              <span className="environment-tag">NOT YET ACTIVE</span>
            </section>
          )}

          <footer className="footer">
            <span>COMMONPAY · GOLDX TECHNOLOGIES</span>
            <span>Your money. Your control. One command centre.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}

export default App;

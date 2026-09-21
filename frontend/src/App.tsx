import {
  ArrowUpRight,
  Bookmark,
  BriefcaseBusiness,
  CheckCircle2,
  FileText,
  Heart,
  Home,
  Languages,
  LogOut,
  Menu,
  Search,
  Settings2,
  Sparkles,
  Target,
  Upload,
  UserRound,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Locale, messages } from "./i18n";

type Page = "dashboard" | "jobs" | "matches" | "applications" | "resume" | "profile";

type Job = {
  id: string;
  source: string;
  title: string;
  company: string;
  location: string;
  remote_region: string;
  tags: string[];
  salary_min: number | null;
  salary_max: number | null;
  currency: string;
  url: string;
  published_at: string | null;
};

type Match = {
  id: string;
  score: number;
  matching_skills: string[];
  skill_gaps: string[];
  reasons: string[];
  verdict: "apply" | "maybe" | "skip";
  job: Job;
};

type Profile = {
  id?: string;
  user_id?: string;
  headline: string;
  summary: string;
  years_experience: number;
  english_level: string;
  skills: string[];
  target_roles: string[];
  preferred_regions: string[];
  min_salary_usd: number | null;
  remote_only: boolean;
  exclude_keywords: string[];
};

type Stats = {
  jobs_total: number;
  strong_matches: number;
  saved: number;
  applied: number;
  interviews: number;
  offers: number;
};

type Application = {
  id: string;
  status: string;
  notes: string;
  tailored_summary: string;
  cover_letter: string;
  job: Job;
};

const API = import.meta.env.VITE_API_URL || "http://localhost:8030/api/v1";

function splitCsv(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function salary(job: Job, unknown: string) {
  if (!job.salary_min && !job.salary_max) return unknown;
  const formatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: job.currency || "USD",
    maximumFractionDigits: 0,
  });
  if (job.salary_min && job.salary_max) {
    return `${formatter.format(job.salary_min)} – ${formatter.format(job.salary_max)}`;
  }
  return formatter.format(job.salary_min || job.salary_max || 0);
}

function App() {
  const [locale, setLocale] = useState<Locale>(
    (localStorage.getItem("jobscout_locale") as Locale) || "en"
  );
  const t = messages[locale];
  const [token, setToken] = useState(localStorage.getItem("jobscout_token") || "");
  const [displayName, setDisplayName] = useState(localStorage.getItem("jobscout_name") || "Pinkkkie");
  const [page, setPage] = useState<Page>("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [profile, setProfile] = useState<Profile>({
    headline: "",
    summary: "",
    years_experience: 0,
    english_level: "",
    skills: [],
    target_roles: [],
    preferred_regions: [],
    min_salary_usd: null,
    remote_only: true,
    exclude_keywords: [],
  });
  const [search, setSearch] = useState("");
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");
  const [selectedApplication, setSelectedApplication] = useState<Application | null>(null);

  const api = useCallback(
    async (path: string, options: RequestInit = {}) => {
      const headers = new Headers(options.headers || {});
      if (token) headers.set("Authorization", `Bearer ${token}`);
      if (!(options.body instanceof FormData) && options.body) {
        headers.set("Content-Type", "application/json");
      }
      const response = await fetch(`${API}${path}`, { ...options, headers });
      if (response.status === 401) {
        localStorage.removeItem("jobscout_token");
        setToken("");
      }
      if (!response.ok) {
        const data = await response.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(data.detail || "Request failed");
      }
      if (response.status === 204) return null;
      return response.json();
    },
    [token]
  );

  const refresh = useCallback(async () => {
    if (!token) return;
    setError("");
    try {
      const [statsData, matchData, jobsData, appData, profileData] = await Promise.all([
        api("/dashboard/stats"),
        api("/jobs/matches?limit=50"),
        api("/jobs?limit=80"),
        api("/applications"),
        api("/profile"),
      ]);
      setStats(statsData);
      setMatches(matchData);
      setJobs(jobsData);
      setApplications(appData);
      setProfile(profileData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    }
  }, [api, token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const changeLocale = () => {
    const next = locale === "en" ? "ru" : "en";
    setLocale(next);
    localStorage.setItem("jobscout_locale", next);
  };

  const scanJobs = async () => {
    setScanning(true);
    setError("");
    try {
      await api("/jobs/scan", { method: "POST" });
      window.setTimeout(async () => {
        await refresh();
        setScanning(false);
      }, 3500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
      setScanning(false);
    }
  };

  if (!token) {
    return (
      <AuthScreen
        locale={locale}
        onLocale={changeLocale}
        onAuthenticated={(newToken, name) => {
          localStorage.setItem("jobscout_token", newToken);
          localStorage.setItem("jobscout_name", name || "Pinkkkie");
          setDisplayName(name || "Pinkkkie");
          setToken(newToken);
        }}
      />
    );
  }

  const navigation = [
    { id: "dashboard" as Page, label: t.dashboard, icon: Home },
    { id: "jobs" as Page, label: t.jobs, icon: BriefcaseBusiness },
    { id: "matches" as Page, label: t.matches, icon: Heart },
    { id: "applications" as Page, label: t.applications, icon: FileText },
    { id: "resume" as Page, label: t.resume, icon: Upload },
    { id: "profile" as Page, label: t.profile, icon: UserRound },
  ];

  const visibleJobs = jobs.filter((job) => {
    const needle = search.toLowerCase();
    return (
      !needle ||
      job.title.toLowerCase().includes(needle) ||
      job.company.toLowerCase().includes(needle) ||
      job.tags.join(" ").toLowerCase().includes(needle)
    );
  });

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <button className="mobile-close" onClick={() => setSidebarOpen(false)} aria-label="Close menu">
          <X size={20} />
        </button>
        <Brand />
        <nav>
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={page === id ? "nav-item active" : "nav-item"}
              onClick={() => {
                setPage(id);
                setSidebarOpen(false);
              }}
            >
              <Icon size={19} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-card">
          <Sparkles size={22} />
          <strong>{locale === "en" ? "Your next opportunity has no borders." : "Твоя следующая работа не знает границ."}</strong>
          <span>{locale === "en" ? "AI-curated remote jobs from around the world." : "Подходящие remote-вакансии со всего мира."}</span>
        </div>
        <button
          className="nav-item logout"
          onClick={() => {
            localStorage.removeItem("jobscout_token");
            setToken("");
          }}
        >
          <LogOut size={18} />
          {t.logout}
        </button>
      </aside>

      {sidebarOpen && <div className="backdrop" onClick={() => setSidebarOpen(false)} />}

      <main className="main">
        <header className="topbar">
          <button className="menu-button" onClick={() => setSidebarOpen(true)} aria-label="Menu">
            <Menu size={22} />
          </button>
          <div className="global-search">
            <Search size={19} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t.searchPlaceholder}
            />
          </div>
          <div className="top-actions">
            <span className="remote-pill">🌐 {t.remote}</span>
            <button className="icon-button locale-button" onClick={changeLocale}>
              <Languages size={18} />
              {t.language}
            </button>
            <div className="user-chip">
              <div className="avatar">{displayName.slice(0, 1).toUpperCase()}</div>
              <div>
                <strong>{displayName}</strong>
                <span>{locale === "en" ? "Good things ahead!" : "Все впереди!"}</span>
              </div>
            </div>
          </div>
        </header>

        <section className="content">
          {error && <div className="error-banner">{error}</div>}

          {page === "dashboard" && (
            <DashboardPage
              locale={locale}
              name={displayName}
              stats={stats}
              matches={matches}
              onScan={scanJobs}
              scanning={scanning}
              onPrepare={async (jobId) => {
                const app = await api(`/applications/${jobId}/prepare`, { method: "POST" });
                setSelectedApplication(app);
                await refresh();
              }}
            />
          )}

          {page === "jobs" && (
            <JobsPage
              jobs={visibleJobs}
              locale={locale}
              onSave={async (jobId) => {
                await api(`/applications/${jobId}`, {
                  method: "PUT",
                  body: JSON.stringify({ status: "saved", notes: "" }),
                });
                await refresh();
              }}
              onScan={scanJobs}
              scanning={scanning}
            />
          )}

          {page === "matches" && (
            <MatchesPage
              matches={matches}
              locale={locale}
              onPrepare={async (jobId) => {
                const app = await api(`/applications/${jobId}/prepare`, { method: "POST" });
                setSelectedApplication(app);
                await refresh();
              }}
              onApplied={async (jobId) => {
                await api(`/applications/${jobId}`, {
                  method: "PUT",
                  body: JSON.stringify({ status: "applied", notes: "" }),
                });
                await refresh();
              }}
            />
          )}

          {page === "applications" && (
            <ApplicationsPage applications={applications} locale={locale} />
          )}

          {page === "resume" && (
            <ResumePage
              locale={locale}
              api={api}
              onUploaded={async () => {
                await refresh();
                setPage("profile");
              }}
            />
          )}

          {page === "profile" && (
            <ProfilePage
              locale={locale}
              profile={profile}
              onSave={async (value) => {
                const saved = await api("/profile", {
                  method: "PUT",
                  body: JSON.stringify(value),
                });
                setProfile(saved);
                await refresh();
              }}
            />
          )}
        </section>
      </main>

      <nav className="mobile-nav">
        {navigation.slice(0, 5).map(({ id, label, icon: Icon }) => (
          <button key={id} className={page === id ? "active" : ""} onClick={() => setPage(id)}>
            <Icon size={19} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {selectedApplication && (
        <ApplicationModal
          application={selectedApplication}
          locale={locale}
          onClose={() => setSelectedApplication(null)}
        />
      )}
    </div>
  );
}

function Brand() {
  return (
    <div className="brand">
      <img src="/brand-icon.svg" alt="" />
      <div>
        <strong>JobScout AI</strong>
        <span>Global opportunities</span>
      </div>
    </div>
  );
}

function AuthScreen({
  locale,
  onLocale,
  onAuthenticated,
}: {
  locale: Locale;
  onLocale: () => void;
  onAuthenticated: (token: string, name: string) => void;
}) {
  const t = messages[locale];
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("Pinkkkie");
  const [error, setError] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      if (mode === "register") {
        const registerResponse = await fetch(`${API}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password, display_name: name, locale }),
        });
        if (!registerResponse.ok) {
          const data = await registerResponse.json();
          throw new Error(data.detail || "Registration failed");
        }
      }
      const response = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Login failed");
      }
      const data = await response.json();
      onAuthenticated(data.access_token, name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    }
  };

  return (
    <div className="auth-page">
      <button className="auth-language" onClick={onLocale}>
        <Languages size={17} /> {t.language}
      </button>
      <section className="auth-brand-panel">
        <div className="auth-copy">
          <Brand />
          <h1>{locale === "en" ? "A smarter path to your next job." : "Умный путь к следующей работе."}</h1>
          <p>
            {locale === "en"
              ? "JobScout searches, filters and explains international remote opportunities around your profile."
              : "JobScout ищет, фильтрует и объясняет международные remote-вакансии именно под твой профиль."}
          </p>
          <div className="auth-feature-grid">
            <span>✦ AI matching</span>
            <span>✦ Resume parsing</span>
            <span>✦ Remote jobs</span>
            <span>✦ Application tracker</span>
          </div>
        </div>
      </section>
      <section className="auth-form-panel">
        <form className="auth-card" onSubmit={submit}>
          <Sparkles className="pink" />
          <h2>{mode === "login" ? t.login : t.register}</h2>
          <p>{t.authSubtitle}</p>
          {mode === "register" && (
            <label>
              {t.name}
              <input value={name} onChange={(event) => setName(event.target.value)} required />
            </label>
          )}
          <label>
            {t.email}
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          <label>
            {t.password}
            <input
              type="password"
              minLength={10}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error && <div className="field-error">{error}</div>}
          <button className="primary-button" type="submit">
            {mode === "login" ? t.login : t.register}
          </button>
          <button
            className="text-button"
            type="button"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login" ? t.switchRegister : t.switchLogin}
          </button>
        </form>
      </section>
    </div>
  );
}

function DashboardPage({
  locale,
  name,
  stats,
  matches,
  onScan,
  scanning,
  onPrepare,
}: {
  locale: Locale;
  name: string;
  stats: Stats | null;
  matches: Match[];
  onScan: () => void;
  scanning: boolean;
  onPrepare: (jobId: string) => Promise<void>;
}) {
  const t = messages[locale];
  const cards = [
    [t.newJobs, stats?.jobs_total || 0, BriefcaseBusiness],
    [t.strongMatches, stats?.strong_matches || 0, Heart],
    [t.saved, stats?.saved || 0, Bookmark],
    [t.applied, stats?.applied || 0, CheckCircle2],
  ] as const;

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">JOBSCOUT AI</span>
          <h1>{t.welcome}, {name} 👋</h1>
          <p>{t.subtitle}</p>
        </div>
        <button className="primary-button scan-button" onClick={onScan} disabled={scanning}>
          <Sparkles size={18} />
          {scanning ? t.scanning : t.scan}
        </button>
      </div>

      <div className="stat-grid">
        {cards.map(([label, value, Icon]) => (
          <article className="stat-card" key={label}>
            <div className="stat-icon"><Icon size={21} /></div>
            <div><span>{label}</span><strong>{value}</strong></div>
          </article>
        ))}
      </div>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-title">
            <div><Sparkles size={20} /><h2>{t.topMatches}</h2></div>
            <span className="muted">{matches.length}</span>
          </div>
          <div className="match-list">
            {matches.slice(0, 6).map((match) => (
              <MatchRow key={match.id} match={match} locale={locale} onPrepare={onPrepare} />
            ))}
            {!matches.length && <EmptyState text={t.noMatches} />}
          </div>
        </section>

        <aside className="dashboard-side">
          <section className="panel priority-card">
            <Target size={22} />
            <h3>{locale === "en" ? "Today’s focus" : "Фокус на сегодня"}</h3>
            <p>{locale === "en" ? "Review strong matches and send 2 thoughtful applications." : "Посмотри сильные совпадения и отправь 2 качественных отклика."}</p>
            <div className="progress-line"><span style={{ width: "56%" }} /></div>
          </section>
          <section className="panel install-card">
            <img src="/brand-icon.svg" alt="" />
            <h3>{t.installTitle}</h3>
            <p>{t.installText}</p>
          </section>
        </aside>
      </div>
    </>
  );
}

function MatchRow({
  match,
  locale,
  onPrepare,
}: {
  match: Match;
  locale: Locale;
  onPrepare: (jobId: string) => Promise<void>;
}) {
  const t = messages[locale];
  return (
    <article className="match-row">
      <div className="company-badge">{match.job.company.slice(0, 1).toUpperCase()}</div>
      <div className="match-main">
        <div className="match-heading">
          <div>
            <h3>{match.job.title}</h3>
            <p>{match.job.company} · {match.job.location || match.job.remote_region}</p>
          </div>
          <div className={`score-ring ${match.verdict}`}><strong>{Math.round(match.score)}%</strong><span>{t.fit}</span></div>
        </div>
        <div className="salary-line">{salary(match.job, t.salaryUnknown)} · {t.source}: {match.job.source}</div>
        <div className="skill-row">
          {match.matching_skills.slice(0, 4).map((skill) => <span className="tag positive" key={skill}>{skill}</span>)}
          {match.skill_gaps.slice(0, 2).map((skill) => <span className="tag gap" key={skill}>{skill}</span>)}
        </div>
      </div>
      <button className="soft-button" onClick={() => onPrepare(match.job.id)}>
        {t.prepare} <ArrowUpRight size={16} />
      </button>
    </article>
  );
}

function JobsPage({
  jobs,
  locale,
  onSave,
  onScan,
  scanning,
}: {
  jobs: Job[];
  locale: Locale;
  onSave: (jobId: string) => Promise<void>;
  onScan: () => void;
  scanning: boolean;
}) {
  const t = messages[locale];
  return (
    <>
      <div className="page-heading">
        <div><span className="eyebrow">{t.remote}</span><h1>{t.jobs}</h1><p>{locale === "en" ? "Fresh roles from attributed public sources." : "Свежие вакансии из разрешенных публичных источников."}</p></div>
        <button className="primary-button" onClick={onScan} disabled={scanning}><Sparkles size={18} />{scanning ? t.scanning : t.scan}</button>
      </div>
      <div className="job-grid">
        {jobs.map((job) => (
          <article className="job-card" key={job.id}>
            <div className="job-card-head"><div className="company-badge">{job.company.slice(0,1).toUpperCase()}</div><button className="bookmark-button" onClick={() => onSave(job.id)}><Bookmark size={18}/></button></div>
            <h3>{job.title}</h3>
            <p>{job.company}</p>
            <div className="job-meta"><span>🌐 {job.location || job.remote_region}</span><span>{salary(job,t.salaryUnknown)}</span></div>
            <div className="skill-row">{job.tags.slice(0,5).map(tag=><span className="tag" key={tag}>{tag}</span>)}</div>
            <div className="job-actions"><span className="source-label">{job.source}</span><a className="soft-button" href={job.url} target="_blank" rel="noreferrer">{t.openOriginal}<ArrowUpRight size={15}/></a></div>
          </article>
        ))}
      </div>
    </>
  );
}

function MatchesPage({
  matches,
  locale,
  onPrepare,
  onApplied,
}: {
  matches: Match[];
  locale: Locale;
  onPrepare: (jobId: string) => Promise<void>;
  onApplied: (jobId: string) => Promise<void>;
}) {
  const t = messages[locale];
  return (
    <>
      <div className="page-heading"><div><span className="eyebrow">AI MATCHING</span><h1>{t.matches}</h1><p>{locale === "en" ? "Ranked against your profile, preferences and skills." : "Рейтинг относительно твоего профиля, навыков и предпочтений."}</p></div></div>
      <div className="match-detail-list">
        {matches.map(match => (
          <article className="panel match-detail" key={match.id}>
            <div className="match-detail-top">
              <div><span className={`verdict ${match.verdict}`}>{t[match.verdict]}</span><h2>{match.job.title}</h2><p>{match.job.company} · {match.job.location}</p></div>
              <div className={`big-score ${match.verdict}`}><strong>{Math.round(match.score)}%</strong><span>{t.fit}</span></div>
            </div>
            <div className="analysis-grid">
              <div><h4>✓ {t.matchingSkills}</h4><div className="skill-row">{match.matching_skills.map(skill=><span className="tag positive" key={skill}>{skill}</span>)}</div></div>
              <div><h4>! {t.skillGaps}</h4><div className="skill-row">{match.skill_gaps.map(skill=><span className="tag gap" key={skill}>{skill}</span>)}</div></div>
            </div>
            <div className="reason-list">{match.reasons.map(reason=><span key={reason}>✦ {reason}</span>)}</div>
            <div className="job-actions">
              <a className="ghost-button" href={match.job.url} target="_blank" rel="noreferrer">{t.openOriginal}<ArrowUpRight size={15}/></a>
              <button className="ghost-button" onClick={()=>onApplied(match.job.id)}>{t.markApplied}</button>
              <button className="primary-button" onClick={()=>onPrepare(match.job.id)}>{t.prepare}<Sparkles size={16}/></button>
            </div>
          </article>
        ))}
        {!matches.length && <EmptyState text={t.noMatches}/>}
      </div>
    </>
  );
}

function ApplicationsPage({ applications, locale }: { applications: Application[]; locale: Locale }) {
  const t = messages[locale];
  return (
    <>
      <div className="page-heading"><div><span className="eyebrow">PIPELINE</span><h1>{t.tracker}</h1><p>{locale === "en" ? "Everything you applied to, in one place." : "Все твои отклики и их статусы в одном месте."}</p></div></div>
      <section className="panel table-panel">
        {applications.map(app=>(
          <div className="application-row" key={app.id}>
            <div className="company-badge">{app.job.company.slice(0,1).toUpperCase()}</div>
            <div><strong>{app.job.title}</strong><span>{app.job.company}</span></div>
            <span className={`status-pill ${app.status}`}>{app.status}</span>
            <a href={app.job.url} target="_blank" rel="noreferrer"><ArrowUpRight size={18}/></a>
          </div>
        ))}
        {!applications.length && <EmptyState text={t.noApplications}/>}
      </section>
    </>
  );
}

function ResumePage({
  locale,
  api,
  onUploaded,
}: {
  locale: Locale;
  api: (path:string, options?:RequestInit)=>Promise<any>;
  onUploaded: ()=>Promise<void>;
}) {
  const t=messages[locale];
  const [file,setFile]=useState<File|null>(null);
  const [busy,setBusy]=useState(false);
  const [result,setResult]=useState<any>(null);
  const submit=async()=>{
    if(!file)return;
    setBusy(true);
    const data=new FormData();
    data.append("file",file);
    const uploaded=await api("/resumes",{method:"POST",body:data});
    setResult(uploaded);
    setBusy(false);
    await onUploaded();
  };
  return (
    <>
      <div className="page-heading"><div><span className="eyebrow">AI PROFILE</span><h1>{t.uploadResume}</h1><p>{locale==="en"?"Upload once, review the extracted profile, then edit anything you want.":"Загрузи резюме, проверь извлеченный профиль и исправь все, что нужно."}</p></div></div>
      <div className="resume-layout">
        <section className="panel upload-zone">
          <Upload size={42}/>
          <h2>{t.chooseFile}</h2>
          <p>PDF / DOCX / TXT · max 10 MB</p>
          <input type="file" accept=".pdf,.docx,.txt" onChange={e=>setFile(e.target.files?.[0]||null)}/>
          {file&&<strong>{file.name}</strong>}
          <button className="primary-button" disabled={!file||busy} onClick={submit}>{busy?"Analyzing…":t.upload}</button>
        </section>
        <section className="panel parsing-preview">
          <Sparkles size={22}/>
          <h3>{locale==="en"?"AI parsing preview":"Предпросмотр AI-разбора"}</h3>
          {result ? <pre>{JSON.stringify(result.extracted_profile,null,2)}</pre> : <p>{locale==="en"?"Your extracted roles, skills and experience will appear here.":"Здесь появятся найденные роли, навыки и опыт."}</p>}
        </section>
      </div>
    </>
  );
}

function ProfilePage({
  locale,
  profile,
  onSave,
}: {
  locale: Locale;
  profile: Profile;
  onSave: (profile: Profile)=>Promise<void>;
}) {
  const t=messages[locale];
  const [draft,setDraft]=useState(profile);
  const [saveState,setSaveState]=useState<"idle"|"saving"|"saved"|"error">("idle");
  const [saveError,setSaveError]=useState("");
  useEffect(()=>setDraft(profile),[profile]);
  const update=(patch:Partial<Profile>)=>{
    setDraft(current=>({...current,...patch}));
    setSaveState("idle");
    setSaveError("");
  };
  const save=async()=>{
    setSaveState("saving");
    setSaveError("");
    try{
      await onSave(draft);
      setSaveState("saved");
      window.setTimeout(()=>setSaveState(current=>current==="saved"?"idle":current),2500);
    }catch(err){
      setSaveError(err instanceof Error?err.message:"Save failed");
      setSaveState("error");
    }
  };
  const buttonText =
    saveState==="saving"
      ? (locale==="en"?"Saving…":"Сохраняем…")
      : saveState==="saved"
        ? (locale==="en"?"Saved ✓":"Сохранено ✓")
        : t.saveProfile;
  return (
    <>
      <div className="page-heading"><div><span className="eyebrow">PERSONALIZATION</span><h1>{t.profile}</h1><p>{t.profileHelp}</p></div></div>
      <section className="panel profile-form">
        <label>{t.targetRoles}<input value={draft.target_roles.join(", ")} onChange={e=>update({target_roles:splitCsv(e.target.value)})} placeholder="Python Developer, Backend Developer, AI Developer"/></label>
        <label>{t.skills}<textarea value={draft.skills.join(", ")} onChange={e=>update({skills:splitCsv(e.target.value)})} placeholder="Python, FastAPI, PostgreSQL, Docker, RAG…"/></label>
        <div className="form-grid">
          <label>{t.years}<input type="number" min="0" max="60" value={draft.years_experience} onChange={e=>update({years_experience:Number(e.target.value)})}/></label>
          <label>{t.english}<select value={draft.english_level} onChange={e=>update({english_level:e.target.value})}><option value="">—</option><option>A2</option><option>B1</option><option>B2</option><option>C1</option><option>C2</option></select></label>
        </div>
        <label>{t.regions}<input value={draft.preferred_regions.join(", ")} onChange={e=>update({preferred_regions:splitCsv(e.target.value)})} placeholder="Worldwide, Europe, EMEA"/></label>
        <div className="form-grid">
          <label>{t.salary}<input type="number" value={draft.min_salary_usd??""} onChange={e=>update({min_salary_usd:e.target.value?Number(e.target.value):null})}/></label>
          <label className="checkbox-label"><input type="checkbox" checked={draft.remote_only} onChange={e=>update({remote_only:e.target.checked})}/>{locale==="en"?"Remote only":"Только удаленка"}</label>
        </div>
        <label>{t.exclude}<input value={draft.exclude_keywords.join(", ")} onChange={e=>update({exclude_keywords:splitCsv(e.target.value)})} placeholder="onsite, PHP, 7+ years"/></label>
        <label>{locale==="en"?"Professional summary":"О себе"}<textarea value={draft.summary} onChange={e=>update({summary:e.target.value})}/></label>
        <div className="profile-save-row">
          <button className={"primary-button profile-save "+(saveState==="saved"?"saved":"")} disabled={saveState==="saving"} onClick={save}>{buttonText}</button>
          {saveState==="saved"&&<span className="save-success">{locale==="en"?"Profile updated successfully":"Профиль успешно обновлен"}</span>}
          {saveState==="error"&&<span className="save-error">{saveError}</span>}
        </div>
      </section>
      <section className="panel install-guide">
        <img src="/brand-icon.svg" alt=""/>
        <div><h3>{t.installTitle}</h3><p>{t.installText}</p></div>
      </section>
    </>
  );
}

function ApplicationModal({application,locale,onClose}:{application:Application;locale:Locale;onClose:()=>void}) {
  const t=messages[locale];
  return <div className="modal-backdrop" onClick={onClose}><div className="modal-card" onClick={e=>e.stopPropagation()}>
    <button className="modal-close" onClick={onClose}><X/></button>
    <span className="eyebrow">APPLICATION PACK</span>
    <h2>{application.job.title}</h2>
    <p className="muted">{application.job.company}</p>
    <h3>{t.tailoredSummary}</h3><div className="copy-box">{application.tailored_summary}</div>
    <h3>{t.coverLetter}</h3><div className="copy-box letter">{application.cover_letter}</div>
    <a className="primary-button link-button" href={application.job.url} target="_blank" rel="noreferrer">{t.openOriginal}<ArrowUpRight size={16}/></a>
  </div></div>;
}

function EmptyState({text}:{text:string}) {
  return <div className="empty-state"><Sparkles size={28}/><span>{text}</span></div>;
}

export default App;

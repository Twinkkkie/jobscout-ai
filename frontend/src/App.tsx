import {
  ArrowUpRight,
  Bookmark,
  BriefcaseBusiness,
  CheckCircle2,
  FileText,
  Heart,
  Home,
  Languages,
  LoaderCircle,
  LogOut,
  Menu,
  Search,
  Settings2,
  Sparkles,
  Target,
  Trash2,
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
  collected_at: string;
  last_checked_at: string | null;
  is_active: boolean;
  closed_at: string | null;
  ai_analysis?: Record<string, unknown>;
  ai_analyzed_at?: string | null;
};

type Match = {
  id: string;
  score: number;
  matching_skills: string[];
  skill_gaps: string[];
  reasons: string[];
  verdict: "apply" | "maybe" | "skip";
  ai_explanation?: {
    summary?: string;
    strengths?: string[];
    gaps?: string[];
    transferable_skills?: string[];
    application_advice?: string[];
    ai_enriched?: boolean;
  };
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
  seniority_levels: string[];
  preferred_regions: string[];
  min_salary_usd: number | null;
  remote_only: boolean;
  exclude_keywords: string[];
  rematch_queued?: boolean;
  rematch_task_id?: string | null;
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
  recruiter_message: string;
  interview_points: string[];
  caution_notes: string[];
  agent_trace: string[];
  job: Job;
};

type CareerInsight = {
  summary: string;
  recurring_gaps: string[];
  strongest_skills: string[];
  target_role_observations: string[];
  recommended_actions: string[];
  ai_enriched: boolean;
  agent: string;
  engine: string;
  trace: string[];
};

type AgentStatus = {
  openai_configured: boolean;
  model: string;
  langgraph_available: boolean;
  agents: string[];
  human_review_required: boolean;
};

const API = import.meta.env.VITE_API_URL || "http://localhost:8030/api/v1";

function splitCsv(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function decodeHtmlEntities(value: string) {
  if (!value) return "";
  const textarea = document.createElement("textarea");
  textarea.innerHTML = value;
  return textarea.value;
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
    seniority_levels: [],
    preferred_regions: [],
    min_salary_usd: null,
    remote_only: true,
    exclude_keywords: [],
  });
  const [search, setSearch] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanNotice, setScanNotice] = useState("");
  const [error, setError] = useState("");
  const [selectedApplication, setSelectedApplication] = useState<Application | null>(null);
  const [preparingApplication, setPreparingApplication] = useState<Job | null>(null);
  const [prepareStage, setPrepareStage] = useState("");
  const [careerInsight, setCareerInsight] = useState<CareerInsight | null>(null);
  const [careerLoading, setCareerLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);

  const api = useCallback(
    async (path: string, options: RequestInit = {}) => {
      const headers = new Headers(options.headers || {});
      if (token) headers.set("Authorization", `Bearer ${token}`);
      if (!(options.body instanceof FormData) && options.body) {
        headers.set("Content-Type", "application/json");
      }
      let response: Response;
      try {
        response = await fetch(`${API}${path}`, { ...options, headers });
      } catch {
        throw new Error(
          locale === "en"
            ? "Cannot reach the JobScout API. Check that Docker/API is running."
            : "Не удается подключиться к API JobScout. Проверь, что Docker/API запущен."
        );
      }
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
    [token, locale]
  );

  const refresh = useCallback(async () => {
    if (!token) return;
    setError("");
    try {
      const [statsData, matchData, jobsData, appData, profileData, agentStatusData] = await Promise.all([
        api("/dashboard/stats"),
        api("/jobs/matches?limit=200"),
        api("/jobs?limit=200"),
        api("/applications"),
        api("/profile"),
        api("/agents/status"),
      ]);
      setStats(statsData);
      setMatches(matchData);
      setJobs(jobsData);
      setApplications(appData);
      setProfile(profileData);
      setAgentStatus(agentStatusData);
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
    setScanNotice("");
    setError("");
    try {
      const queued = await api("/jobs/scan", { method: "POST" });
      const taskId = queued.task_id;
      let completed = false;

      for (let attempt = 0; attempt < 25; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        const state = await api(`/jobs/scan/${taskId}`);

        if (state.status === "success") {
          completed = true;
          const result = state.result || {};
          const newJobs = Number(result.new_jobs || 0);
          const closedJobs = Number(result.availability?.closed || 0);
          const aiTaskId = result.ai_task_id as string | undefined;
          setScanNotice(
            locale === "en"
              ? `${newJobs} new vacancies added${closedJobs ? ` · ${closedJobs} closed removed` : ""}${aiTaskId ? " · AI is refining matches in the background" : ""}`
              : `Добавлено новых вакансий: ${newJobs}${closedJobs ? ` · закрытых убрано: ${closedJobs}` : ""}${aiTaskId ? " · AI уточняет мэтчи в фоне" : ""}`
          );
          await refresh();

          if (aiTaskId) {
            void (async () => {
              for (let aiAttempt = 0; aiAttempt < 30; aiAttempt += 1) {
                await new Promise((resolve) => window.setTimeout(resolve, 1000));
                try {
                  const aiState = await api(`/jobs/scan/${aiTaskId}`);
                  if (aiState.status === "success") {
                    const aiJobs = Number(aiState.result?.ai_enriched_jobs || 0);
                    await refresh();
                    setScanNotice(
                      locale === "en"
                        ? `${newJobs} new vacancies added · AI refreshed ${aiJobs} promising vacancies`
                        : `Добавлено новых вакансий: ${newJobs} · AI обновил ${aiJobs} перспективных вакансий`
                    );
                    break;
                  }
                  if (aiState.status === "failure") break;
                } catch {
                  break;
                }
              }
            })();
          }
          break;
        }

        if (state.status === "failure") {
          throw new Error(state.error || "Job scan failed");
        }
      }

      if (!completed) {
        setScanNotice(
          locale === "en"
            ? "Scan is still running in the background. You can keep using JobScout."
            : "Поиск продолжается в фоне. JobScout можно продолжать использовать."
        );

        void (async () => {
          for (let attempt = 0; attempt < 120; attempt += 1) {
            await new Promise(resolve => window.setTimeout(resolve, 1000));
            try {
              const state = await api(`/jobs/scan/${taskId}`);
              if (state.status === "success") {
                await refresh();
                const result = state.result || {};
                const newJobs = Number(result.new_jobs || 0);
                setScanNotice(
                  locale === "en"
                    ? `Scan finished · ${newJobs} new vacancies added`
                    : `Поиск завершен · добавлено новых вакансий: ${newJobs}`
                );
                break;
              }
              if (state.status === "failure") {
                setScanNotice(
                  locale === "en"
                    ? "Background scan failed. Try again."
                    : "Фоновый поиск завершился с ошибкой. Попробуй еще раз."
                );
                break;
              }
            } catch {
              break;
            }
          }
        })();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  };

  const prepareApplication = async (jobId: string) => {
    const job =
      jobs.find(item => item.id === jobId) ||
      matches.find(item => item.job.id === jobId)?.job ||
      applications.find(item => item.job.id === jobId)?.job;

    if (job) setPreparingApplication(job);
    setPrepareStage(locale === "en" ? "Starting Application Agent…" : "Запускаем Application Agent…");
    setError("");

    try {
      const queued = await api(`/applications/${jobId}/prepare`, { method: "POST" });

      if (queued.status === "ready" && queued.application) {
        setSelectedApplication(queued.application as Application);
        setPreparingApplication(null);
        setPrepareStage("");
        return;
      }

      const taskId = queued.task_id as string | undefined;
      if (!taskId) throw new Error(locale === "en" ? "Could not start application preparation." : "Не удалось запустить подготовку отклика.");

      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise(resolve => window.setTimeout(resolve, 500));
        const state = await api(`/jobs/scan/${taskId}`);

        const stage = state.meta?.stage as string | undefined;
        if (stage === "loading_context") {
          setPrepareStage(locale === "en" ? "Loading your profile, resume and vacancy…" : "Загружаем профиль, резюме и вакансию…");
        } else if (stage === "generating_pack") {
          setPrepareStage(locale === "en" ? "AI is tailoring your application pack…" : "AI готовит персональный пакет отклика…");
        } else if (stage === "saving_pack") {
          setPrepareStage(locale === "en" ? "Finalizing the application…" : "Финализируем отклик…");
        }

        if (state.status === "success") {
          const prepared = await api(`/applications/${jobId}`);
          setSelectedApplication(prepared as Application);
          setApplications(current => {
            const exists = current.some(item => item.job.id === jobId);
            return exists
              ? current.map(item => item.job.id === jobId ? prepared : item)
              : [prepared, ...current];
          });
          setPreparingApplication(null);
          setPrepareStage("");
          void refresh();
          return;
        }

        if (state.status === "failure") {
          throw new Error(state.error || (locale === "en" ? "Application preparation failed." : "Не удалось подготовить отклик."));
        }
      }

      throw new Error(locale === "en" ? "Application preparation is still queued. Try again in a moment." : "Подготовка отклика все еще в очереди. Попробуй снова через несколько секунд.");
    } catch (err) {
      setPreparingApplication(null);
      setPrepareStage("");
      setError(err instanceof Error ? err.message : (locale === "en" ? "Application preparation failed." : "Не удалось подготовить отклик."));
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
              careerInsight={careerInsight}
              careerLoading={careerLoading}
              agentStatus={agentStatus}
              onCareer={async () => {
                setCareerLoading(true);
                try {
                  const insight = await api("/agents/career");
                  setCareerInsight(insight);
                } finally {
                  setCareerLoading(false);
                }
              }}
              onPrepare={prepareApplication}
            />
          )}

          {page === "jobs" && (
            <JobsPage
              jobs={visibleJobs}
              matches={matches}
              applications={applications}
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
              scanNotice={scanNotice}
              onAnalyzeMatch={async (jobId) => {
                const applyMatch = (analyzed: Match) => {
                  setMatches(current => {
                    const exists = current.some(item => item.job.id === analyzed.job.id);
                    const next = exists
                      ? current.map(item => item.job.id === analyzed.job.id ? analyzed : item)
                      : [analyzed, ...current];
                    return [...next].sort((a,b) => b.score - a.score);
                  });
                };

                const result = await api(`/jobs/${jobId}/match-analysis`, { method: "POST" });
                const analyzed = result.match as Match;
                applyMatch(analyzed);

                if (result.ai_pending && result.task_id) {
                  const taskId = result.task_id as string;
                  void (async () => {
                    for (let attempt = 0; attempt < 24; attempt += 1) {
                      await new Promise(resolve => window.setTimeout(resolve, 500));
                      try {
                        const state = await api(`/jobs/scan/${taskId}`);
                        if (state.status === "success") {
                          const refined = await api(`/jobs/${jobId}/match-analysis?queue_ai=false`, { method: "POST" });
                          applyMatch(refined.match as Match);
                          break;
                        }
                        if (state.status === "failure") break;
                      } catch {
                        break;
                      }
                    }
                  })();
                }

                return analyzed;
              }}
            />
          )}

          {page === "matches" && (
            <MatchesPage
              matches={matches}
              applications={applications}
              locale={locale}
              onPrepare={prepareApplication}
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
            <ApplicationsPage
              applications={applications}
              locale={locale}
              onDeleteSaved={async (jobId) => {
                await api(`/applications/${jobId}`, { method: "DELETE" });
                await refresh();
              }}
            />
          )}

          {page === "resume" && (
            <ResumePage
              locale={locale}
              api={api}
              onUploaded={async () => {
                await refresh();
              }}
              onContinue={() => setPage("profile")}
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

                if (saved.rematch_task_id) {
                  const taskId = saved.rematch_task_id as string;
                  void (async () => {
                    for (let attempt = 0; attempt < 60; attempt += 1) {
                      await new Promise(resolve => window.setTimeout(resolve, 500));
                      try {
                        const state = await api(`/jobs/scan/${taskId}`);
                        if (state.status === "success") {
                          await refresh();
                          break;
                        }
                        if (state.status === "failure") break;
                      } catch {
                        break;
                      }
                    }
                  })();
                }
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

      {preparingApplication && (
        <ApplicationPreparingModal
          job={preparingApplication}
          locale={locale}
          stage={prepareStage}
        />
      )}

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
  careerInsight,
  careerLoading,
  agentStatus,
  onCareer,
  onPrepare,
}: {
  locale: Locale;
  name: string;
  stats: Stats | null;
  matches: Match[];
  onScan: () => void;
  scanning: boolean;
  careerInsight: CareerInsight | null;
  careerLoading: boolean;
  agentStatus: AgentStatus | null;
  onCareer: () => Promise<void>;
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
          <section className="panel career-card">
            <Sparkles size={22} />
            <div className="career-title-row">
              <h3>Career Agent</h3>
              {agentStatus&&(
                <span className={`ai-runtime-pill ${agentStatus.openai_configured?"ready":"fallback"}`}>
                  {agentStatus.openai_configured
                    ? (agentStatus.langgraph_available?"AI · LangGraph":"AI · fallback graph")
                    : (locale==="en"?"AI key not configured":"AI-ключ не подключен")}
                </span>
              )}
            </div>
            {careerInsight ? (
              <>
                <p>{careerInsight.summary}</p>
                {!!careerInsight.recurring_gaps.length && (
                  <div className="career-chip-row">
                    {careerInsight.recurring_gaps.slice(0,4).map(gap=><span className="tag gap" key={gap}>{gap}</span>)}
                  </div>
                )}
                <div className="career-actions">
                  {careerInsight.recommended_actions.slice(0,3).map(action=><span key={action}>✦ {action}</span>)}
                </div>
              </>
            ) : (
              <p>{locale === "en"
                ? "Analyze your matches and application history to find repeated gaps and next actions."
                : "Проанализирует мэтчи и историю откликов, найдет повторяющиеся пробелы и следующие шаги."}</p>
            )}
            <button className="ghost-button career-button" onClick={onCareer} disabled={careerLoading}>
              <Sparkles size={15}/>
              {careerLoading
                ? (locale==="en"?"Analyzing…":"Анализируем…")
                : (careerInsight
                  ? (locale==="en"?"Refresh insight":"Обновить анализ")
                  : (locale==="en"?"Analyze my search":"Анализировать поиск"))}
            </button>
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
            <h3>{decodeHtmlEntities(match.job.title)}</h3>
            <p>{decodeHtmlEntities(match.job.company)} · {decodeHtmlEntities(match.job.location || match.job.remote_region)}</p>
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
  matches,
  applications,
  locale,
  onSave,
  onScan,
  scanning,
  scanNotice,
  onAnalyzeMatch,
}: {
  jobs: Job[];
  matches: Match[];
  applications: Application[];
  locale: Locale;
  onSave: (jobId: string) => Promise<void>;
  onScan: () => void;
  scanning: boolean;
  scanNotice: string;
  onAnalyzeMatch: (jobId: string) => Promise<Match>;
}) {
  const t = messages[locale];
  const [savingId,setSavingId]=useState<string|null>(null);
  const [feedback,setFeedback]=useState<string>("");
  const [selectedMatch,setSelectedMatch]=useState<Match|null>(null);
  const [analyzingId,setAnalyzingId]=useState<string|null>(null);
  const matchByJob = useMemo(
    () => new Map(matches.map(match => [match.job.id, match])),
    [matches]
  );
  const sortedJobs = useMemo(
    () => [...jobs].sort((a,b) => (matchByJob.get(b.id)?.score || 0) - (matchByJob.get(a.id)?.score || 0)),
    [jobs, matchByJob]
  );
  const statusByJob = useMemo(
    () => new Map(applications.map(application => [application.job.id, application.status])),
    [applications]
  );

  useEffect(()=>{
    if(!selectedMatch) return;
    const latest=matchByJob.get(selectedMatch.job.id);
    if(latest && latest!==selectedMatch) setSelectedMatch(latest);
  },[matches,selectedMatch?.job.id]);

  const saveJob=async(jobId:string)=>{
    setSavingId(jobId);
    setFeedback("");
    try{
      await onSave(jobId);
      setFeedback(locale==="en"?"Vacancy saved to your tracker ✓":"Вакансия сохранена в трекер ✓");
      window.setTimeout(()=>setFeedback(""),2500);
    }catch(err){
      setFeedback(err instanceof Error?err.message:(locale==="en"?"Could not save the vacancy":"Не удалось сохранить вакансию"));
    }finally{
      setSavingId(null);
    }
  };

  const analyzeMatch=async(jobId:string)=>{
    setAnalyzingId(jobId);
    setFeedback("");
    try{
      const analyzed=await onAnalyzeMatch(jobId);
      setSelectedMatch(analyzed);
    }catch(err){
      setFeedback(err instanceof Error?err.message:(locale==="en"?"Could not analyze match":"Не удалось проанализировать мэтч"));
    }finally{
      setAnalyzingId(null);
    }
  };

  const trackerLabel=(status:string|undefined)=>{
    if(!status)return null;
    if(status==="saved")return locale==="en"?"Saved ✓":"Сохранено ✓";
    if(status==="applied")return locale==="en"?"Applied ✓":"Отклик отправлен ✓";
    if(status==="interview")return locale==="en"?"Interview":"Собеседование";
    if(status==="offer")return locale==="en"?"Offer":"Оффер";
    if(status==="rejected")return locale==="en"?"Rejected":"Отказ";
    return status;
  };

  return (
    <>
      <div className="page-heading">
        <div><span className="eyebrow">{t.remote}</span><h1>{t.jobs}</h1><p>{locale === "en" ? "Fresh roles from attributed public sources." : "Свежие вакансии из разрешенных публичных источников."}</p></div>
        <button className="primary-button" onClick={onScan} disabled={scanning}><Sparkles size={18} />{scanning ? t.scanning : t.scan}</button>
      </div>
      {scanNotice&&<div className="scan-feedback"><Sparkles size={17}/><span>{scanNotice}</span></div>}
      {feedback&&<div className="action-feedback"><CheckCircle2 size={17}/><span>{feedback}</span></div>}
      <div className="job-grid">
        {sortedJobs.map((job) => {
          const status=statusByJob.get(job.id);
          const label=trackerLabel(status);
          const locked=Boolean(status && status!=="saved");
          const match=matchByJob.get(job.id);
          const title=decodeHtmlEntities(job.title);
          const company=decodeHtmlEntities(job.company);
          const visibleTags=(job.tags || []).slice(0,4);
          const hiddenTags=Math.max(0,(job.tags || []).length-visibleTags.length);
          return (
            <article className="job-card" key={job.id}>
              <div className="job-card-head">
                <div className="job-card-leading">
                  <div className="company-badge">{company.slice(0,1).toUpperCase()}</div>
                  {Date.now()-new Date(job.collected_at).getTime() < 24*60*60*1000 && (
                    <span className="new-job-badge">{locale==="en"?"NEW":"НОВАЯ"}</span>
                  )}
                </div>
                <button
                  className={`save-job-button ${status?"tracked":""}`}
                  onClick={() => !locked && saveJob(job.id)}
                  disabled={savingId===job.id || locked || status==="saved"}
                  title={label || (locale==="en"?"Save vacancy":"Сохранить вакансию")}
                >
                  {status ? <CheckCircle2 size={16}/> : <Bookmark size={16}/>}
                  <span>
                    {savingId===job.id
                      ? (locale==="en"?"Saving…":"Сохраняем…")
                      : (label || (locale==="en"?"Save":"Сохранить"))}
                  </span>
                </button>
              </div>

              <div className="job-card-content">
                <h3 className="job-card-title" title={title}>{title}</h3>
                <p className="job-card-company" title={company}>{company}</p>

                <div className="job-meta">
                  <span className="job-meta-line">🌐 <span>{decodeHtmlEntities(job.location || job.remote_region)}</span></span>
                  <span className="job-meta-line">{salary(job,t.salaryUnknown)}</span>
                </div>

                <div className="job-tags">
                  {visibleTags.map((tag,index)=><span className="tag" key={`${tag}-${index}`}>{decodeHtmlEntities(String(tag))}</span>)}
                  {hiddenTags>0&&<span className="tag tag-more">+{hiddenTags}</span>}
                </div>
              </div>

              <div className="job-card-footer">
                <span className="source-label" title={job.source}>{job.source}</span>
                <div className="job-actions">
                  {match&&(
                    <button
                      className="soft-button match-check-button"
                      onClick={()=>analyzeMatch(job.id)}
                      disabled={analyzingId===job.id}
                      title={locale==="en"?"Run AI match analysis":"Запустить AI-анализ мэтча"}
                    >
                      <Target size={15}/>
                      <span className="match-check-label">
                        {analyzingId===job.id
                          ? (locale==="en"?"Analyzing…":"AI-анализ…")
                          : (locale==="en"?"Match":"Мэтч")}
                      </span>
                      <span className="match-score-badge">{Math.round(match.score)}%</span>
                    </button>
                  )}
                  <a className="soft-button open-job-button" href={job.url} target="_blank" rel="noreferrer">
                    <span>{locale==="en"?"Open":"Открыть"}</span>
                    <ArrowUpRight size={15}/>
                  </a>
                </div>
              </div>
            </article>
          );
        })}
      </div>
      {selectedMatch&&(
        <JobMatchModal match={selectedMatch} locale={locale} onClose={()=>setSelectedMatch(null)}/>
      )}
    </>
  );
}


function MatchesPage({
  matches,
  applications,
  locale,
  onPrepare,
  onApplied,
}: {
  matches: Match[];
  applications: Application[];
  locale: Locale;
  onPrepare: (jobId: string) => Promise<void>;
  onApplied: (jobId: string) => Promise<void>;
}) {
  const t = messages[locale];
  const [applyingId,setApplyingId]=useState<string|null>(null);
  const [feedback,setFeedback]=useState("");
  const statusByJob = useMemo(
    () => new Map(applications.map(application => [application.job.id, application.status])),
    [applications]
  );

  const markApplied=async(jobId:string)=>{
    setApplyingId(jobId);
    setFeedback("");
    try{
      await onApplied(jobId);
      setFeedback(locale==="en"?"Marked as applied and added to your tracker ✓":"Отмечено как «Отклик отправлен» и добавлено в трекер ✓");
      window.setTimeout(()=>setFeedback(""),2800);
    }catch(err){
      setFeedback(err instanceof Error?err.message:(locale==="en"?"Could not update application status":"Не удалось обновить статус отклика"));
    }finally{
      setApplyingId(null);
    }
  };

  return (
    <>
      <div className="page-heading"><div><span className="eyebrow">AI MATCHING</span><h1>{t.matches}</h1><p>{locale === "en" ? "Ranked against your profile, preferences and skills." : "Рейтинг относительно твоего профиля, навыков и предпочтений."}</p></div></div>
      {feedback&&<div className="action-feedback"><CheckCircle2 size={17}/><span>{feedback}</span></div>}
      <div className="match-detail-list">
        {matches.map(match => {
          const status=statusByJob.get(match.job.id);
          const alreadyApplied=Boolean(status && status!=="saved");
          const appliedLabel = status==="interview"
            ? (locale==="en"?"Interview":"Собеседование")
            : status==="offer"
              ? (locale==="en"?"Offer":"Оффер")
              : status==="rejected"
                ? (locale==="en"?"Rejected":"Отказ")
                : (locale==="en"?"Applied ✓":"Отклик отправлен ✓");
          return (
            <article className="panel match-detail" key={match.id}>
              <div className="match-detail-top">
                <div><span className={`verdict ${match.verdict}`}>{t[match.verdict]}</span><h2>{decodeHtmlEntities(match.job.title)}</h2><p>{decodeHtmlEntities(match.job.company)} · {decodeHtmlEntities(match.job.location || match.job.remote_region)}</p></div>
                <div className={`big-score ${match.verdict}`}><strong>{Math.round(match.score)}%</strong><span>{t.fit}</span></div>
              </div>
              <div className="analysis-grid">
                <div><h4>✓ {t.matchingSkills}</h4><div className="skill-row">{match.matching_skills.map(skill=><span className="tag positive" key={skill}>{skill}</span>)}</div></div>
                <div><h4>! {t.skillGaps}</h4><div className="skill-row">{match.skill_gaps.map(skill=><span className="tag gap" key={skill}>{skill}</span>)}</div></div>
              </div>
              <div className="reason-list">{match.reasons.map(reason=><span key={reason}>✦ {reason}</span>)}</div>
              <div className="job-actions">
                <a className="ghost-button" href={match.job.url} target="_blank" rel="noreferrer">{t.openOriginal}<ArrowUpRight size={15}/></a>
                <button
                  className={`ghost-button applied-action ${alreadyApplied?"done":""}`}
                  onClick={()=>!alreadyApplied && markApplied(match.job.id)}
                  disabled={applyingId===match.job.id || alreadyApplied}
                >
                  {alreadyApplied?<CheckCircle2 size={16}/>:null}
                  {applyingId===match.job.id
                    ? (locale==="en"?"Saving…":"Сохраняем…")
                    : (alreadyApplied?appliedLabel:t.markApplied)}
                </button>
                <button className="primary-button" onClick={()=>onPrepare(match.job.id)}>{t.prepare}<Sparkles size={16}/></button>
              </div>
            </article>
          );
        })}
        {!matches.length && <EmptyState text={t.noMatches}/>}
      </div>
    </>
  );
}


function ApplicationsPage({
  applications,
  locale,
  onDeleteSaved,
}: {
  applications: Application[];
  locale: Locale;
  onDeleteSaved: (jobId: string) => Promise<void>;
}) {
  const t = messages[locale];
  const [tab,setTab]=useState<"saved"|"pipeline">("saved");
  const [removingId,setRemovingId]=useState<string|null>(null);
  const [feedback,setFeedback]=useState("");

  const saved = applications.filter(app => app.status === "saved");
  const pipeline = applications.filter(app => app.status !== "saved");
  const visible = tab === "saved" ? saved : pipeline;

  const removeSaved=async(jobId:string)=>{
    setRemovingId(jobId);
    setFeedback("");
    try{
      await onDeleteSaved(jobId);
      setFeedback(locale==="en"?"Removed from saved vacancies":"Удалено из сохраненных вакансий");
      window.setTimeout(()=>setFeedback(""),2200);
    }catch(err){
      setFeedback(err instanceof Error?err.message:(locale==="en"?"Could not remove vacancy":"Не удалось удалить вакансию"));
    }finally{
      setRemovingId(null);
    }
  };

  const statusLabel=(status:string)=>{
    const labels:Record<string,string> = locale==="en"
      ? {applied:"Applied",interview:"Interview",offer:"Offer",rejected:"Rejected",withdrawn:"Withdrawn"}
      : {applied:"Отклик отправлен",interview:"Собеседование",offer:"Оффер",rejected:"Отказ",withdrawn:"Отозвано"};
    return labels[status] || status;
  };

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">TRACKER</span>
          <h1>{t.tracker}</h1>
          <p>{locale === "en" ? "Keep saved vacancies separate from jobs you have already applied to." : "Сохраненные вакансии отдельно от тех, на которые ты уже откликнулась."}</p>
        </div>
      </div>

      <div className="tracker-tabs">
        <button className={tab==="saved"?"active":""} onClick={()=>setTab("saved")}>
          <Bookmark size={16}/>
          {locale==="en"?"Saved":"Сохраненные"}
          <span>{saved.length}</span>
        </button>
        <button className={tab==="pipeline"?"active":""} onClick={()=>setTab("pipeline")}>
          <CheckCircle2 size={16}/>
          {locale==="en"?"Applications":"Отклики"}
          <span>{pipeline.length}</span>
        </button>
      </div>

      {feedback&&<div className="action-feedback"><CheckCircle2 size={17}/><span>{feedback}</span></div>}

      <section className="panel table-panel">
        {visible.map(app=>(
          <div className="application-row" key={app.id}>
            <div className="company-badge">{app.job.company.slice(0,1).toUpperCase()}</div>
            <div><strong>{app.job.title}</strong><span>{app.job.company}</span></div>
            <span className={`status-pill ${!app.job.is_active?"closed":app.status}`}>
              {!app.job.is_active
                ? (locale==="en"?"Vacancy closed":"Вакансия закрыта")
                : tab==="saved"
                  ? (locale==="en"?"Saved":"Сохранено")
                  : statusLabel(app.status)}
            </span>
            <div className="application-actions">
              <a href={app.job.url} target="_blank" rel="noreferrer" title={locale==="en"?"Open vacancy":"Открыть вакансию"}><ArrowUpRight size={18}/></a>
              {tab==="saved"&&(
                <button
                  className="delete-saved-button"
                  onClick={()=>removeSaved(app.job.id)}
                  disabled={removingId===app.job.id}
                  title={locale==="en"?"Remove from saved":"Удалить из сохраненных"}
                >
                  <Trash2 size={16}/>
                  <span>{removingId===app.job.id?(locale==="en"?"Removing…":"Удаляем…"):(locale==="en"?"Remove":"Удалить")}</span>
                </button>
              )}
            </div>
          </div>
        ))}
        {!visible.length && (
          <EmptyState
            text={
              tab==="saved"
                ? (locale==="en"?"No saved vacancies yet.":"Сохраненных вакансий пока нет.")
                : (locale==="en"?"No applications yet.":"Откликов пока нет.")
            }
          />
        )}
      </section>
    </>
  );
}


function ResumePage({
  locale,
  api,
  onUploaded,
  onContinue,
}: {
  locale: Locale;
  api: (path:string, options?:RequestInit)=>Promise<any>;
  onUploaded: ()=>Promise<void>;
  onContinue: ()=>void;
}) {
  const t=messages[locale];
  const [file,setFile]=useState<File|null>(null);
  const [busy,setBusy]=useState(false);
  const [result,setResult]=useState<any>(null);
  const [uploadError,setUploadError]=useState("");
  const submit=async()=>{
    if(!file)return;
    setBusy(true);
    setUploadError("");
    const data=new FormData();
    data.append("file",file);
    try{
      const uploaded=await api("/resumes",{method:"POST",body:data});
      setResult(uploaded);
      await onUploaded();
    }catch(err){
      setUploadError(err instanceof Error?err.message:"Resume analysis failed");
    }finally{
      setBusy(false);
    }
  };
  const parsed=result?.extracted_profile;
  return (
    <>
      <div className="page-heading"><div><span className="eyebrow">AI PROFILE</span><h1>{t.uploadResume}</h1><p>{locale==="en"?"Choose a resume, then click Upload & analyze. The extracted profile will appear on the right before you continue.":"Выбери резюме и нажми «Загрузить и проанализировать». Справа появится результат разбора, и только потом можно перейти в профиль."}</p></div></div>
      <div className="resume-layout">
        <section className="panel upload-zone">
          <Upload size={42}/>
          <h2>{t.chooseFile}</h2>
          <p>PDF / DOCX / TXT · max 10 MB</p>
          <div className="custom-file-picker">
            <input
              id="resume-file"
              className="native-file-input"
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={e=>{setFile(e.target.files?.[0]||null);setResult(null);setUploadError("");}}
            />
            <label className="file-picker-button" htmlFor="resume-file">
              <Upload size={17}/>
              {locale==="en"?"Choose file":"Выбрать файл"}
            </label>
            <span className={file?"file-name selected":"file-name"}>
              {file?.name || (locale==="en"?"No file selected":"Файл не выбран")}
            </span>
          </div>
          <button className="primary-button" disabled={!file||busy} onClick={submit}>
            {busy?(locale==="en"?"Analyzing…":"Анализируем…"):t.upload}
          </button>
          {uploadError&&<span className="save-error">{uploadError}</span>}
        </section>
        <section className="panel parsing-preview">
          <Sparkles size={22}/>
          <div className="parsing-title-row">
            <h3>{locale==="en"?"Resume analysis preview":"Предпросмотр разбора резюме"}</h3>
            {result&&<span className="analysis-badge">{locale==="en"?"Parsed":"Разобрано"}</span>}
          </div>
          {!result&&<p>{locale==="en"?"Nothing has been analyzed yet. Choose a file and click Upload & analyze.":"Анализ еще не запускался. Выбери файл и нажми «Загрузить и проанализировать»."}</p>}
          {parsed&&(
            <div className="parsed-profile">
              <div>
                <span className="parsed-label">{locale==="en"?"Target roles":"Целевые роли"}</span>
                <div className="skill-row">{(parsed.target_roles||[]).map((role:string)=><span className="tag positive" key={role}>{role}</span>)}</div>
              </div>
              <div>
                <span className="parsed-label">{locale==="en"?"Skills":"Навыки"}</span>
                <div className="skill-row">{(parsed.skills||[]).map((skill:string)=><span className="tag" key={skill}>{skill}</span>)}</div>
              </div>
              <div className="parsed-kpi">
                <span>{locale==="en"?"Experience detected":"Найденный опыт"}</span>
                <strong>{parsed.years_experience||0} {locale==="en"?"years":"лет"}</strong>
              </div>
              {parsed.summary&&<div><span className="parsed-label">{locale==="en"?"Summary":"Краткое описание"}</span><p>{parsed.summary}</p></div>}
              <button className="primary-button" onClick={onContinue}>
                {locale==="en"?"Review & edit profile":"Проверить и отредактировать профиль"}
                <ArrowUpRight size={16}/>
              </button>
            </div>
          )}
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
        <div className="profile-field">
          <span className="profile-field-label">{locale==="en"?"Target seniority":"Какой грейд ищешь"}</span>
          <div className="seniority-picker">
            {[
              ["intern", locale==="en"?"Intern":"Стажер"],
              ["junior", locale==="en"?"Junior":"Junior"],
              ["middle", locale==="en"?"Middle":"Middle"],
              ["senior", locale==="en"?"Senior":"Senior"],
              ["lead", locale==="en"?"Lead":"Lead"],
            ].map(([value,label])=>{
              const active=draft.seniority_levels.includes(value);
              return <button
                key={value}
                type="button"
                className={active?"active":""}
                onClick={()=>update({
                  seniority_levels: active
                    ? draft.seniority_levels.filter(item=>item!==value)
                    : [...draft.seniority_levels,value]
                })}
              >
                {active&&<CheckCircle2 size={14}/>}
                {label}
              </button>;
            })}
          </div>
          <small>{locale==="en"?"You can select more than one level, for example Junior + Middle.":"Можно выбрать несколько, например Junior + Middle."}</small>
        </div>
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
          {saveState==="saved"&&<span className="save-success">{locale==="en"?"Profile saved ✓ Matches are updating in the background.":"Профиль сохранен ✓ Мэтчи обновляются в фоне."}</span>}
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

function JobMatchModal({match,locale,onClose}:{match:Match;locale:Locale;onClose:()=>void}) {
  const t=messages[locale];
  const explanation=match.ai_explanation || {};
  return <div className="modal-backdrop" onClick={onClose}><div className="modal-card match-modal" onClick={e=>e.stopPropagation()}>
    <button className="modal-close" onClick={onClose}><X/></button>
    <span className="eyebrow">AI MATCH ANALYSIS</span>
    <div className="match-modal-head">
      <div><h2>{decodeHtmlEntities(match.job.title)}</h2><p className="muted">{decodeHtmlEntities(match.job.company)} · {decodeHtmlEntities(match.job.location || match.job.remote_region)}</p></div>
      <div className={`big-score ${match.verdict}`}><strong>{Math.round(match.score)}%</strong><span>{t.fit}</span></div>
    </div>
    {explanation.summary&&(
      <section className="ai-explanation">
        <div className="ai-explanation-title"><Sparkles size={16}/><strong>{locale==="en"?"AI explanation":"AI-разбор"}</strong>{explanation.ai_enriched&&<span>AI</span>}</div>
        <p>{explanation.summary}</p>
        {!!explanation.transferable_skills?.length&&(
          <div><small>{locale==="en"?"Transferable skills":"Переносимые навыки"}</small><div className="skill-row">{explanation.transferable_skills.map(skill=><span className="tag" key={skill}>{skill}</span>)}</div></div>
        )}
        {!!explanation.application_advice?.length&&(
          <div className="ai-advice">{explanation.application_advice.map(item=><span key={item}>✦ {item}</span>)}</div>
        )}
      </section>
    )}
    <div className="analysis-grid">
      <div>
        <h4>✓ {t.matchingSkills} <span className="skill-count">{match.matching_skills.length}</span></h4>
        <div className="skill-row">
          {match.matching_skills.length
            ? match.matching_skills.map(skill=><span className="tag positive" key={skill}>{skill}</span>)
            : <span className="skill-empty">{locale==="en"?"No explicit technical matches detected":"Явных технических совпадений не найдено"}</span>}
        </div>
      </div>
      <div>
        <h4>! {t.skillGaps} <span className="skill-count">{match.skill_gaps.length}</span></h4>
        <div className="skill-row">
          {match.skill_gaps.length
            ? match.skill_gaps.map(skill=><span className="tag gap" key={skill}>{skill}</span>)
            : <span className="skill-empty">{locale==="en"?"No additional explicit technical requirements detected":"Дополнительных явных технических пробелов не найдено"}</span>}
        </div>
      </div>
    </div>
    <div className="reason-list">{match.reasons.map(reason=><span key={reason}>✦ {reason}</span>)}</div>
    <a className="primary-button link-button" href={match.job.url} target="_blank" rel="noreferrer">{t.openOriginal}<ArrowUpRight size={16}/></a>
  </div></div>;
}

function ApplicationPreparingModal({job,locale,stage}:{job:Job;locale:Locale;stage:string}) {
  return <div className="modal-backdrop">
    <div className="modal-card application-preparing-modal">
      <div className="preparing-orb"><LoaderCircle size={32}/></div>
      <span className="eyebrow">APPLICATION AGENT</span>
      <h2>{locale==="en"?"Preparing your application…":"Готовим отклик…"}</h2>
      <p className="muted">{decodeHtmlEntities(job.title)} · {decodeHtmlEntities(job.company)}</p>
      <div className="preparing-stage"><LoaderCircle size={17}/><span>{stage}</span></div>
      <p className="preparing-hint">
        {locale==="en"
          ?"The interface is responsive; generation runs in the background and the finished pack will open automatically."
          :"Генерация идет в фоне. Готовый пакет откроется автоматически сразу после завершения."}
      </p>
    </div>
  </div>;
}

function ApplicationModal({application,locale,onClose}:{application:Application;locale:Locale;onClose:()=>void}) {
  const t=messages[locale];
  const summaryWords=application.tailored_summary.trim().split(/\s+/).filter(Boolean).length;
  const coverWords=application.cover_letter.trim().split(/\s+/).filter(Boolean).length;
  return <div className="modal-backdrop" onClick={onClose}><div className="modal-card application-pack-modal" onClick={e=>e.stopPropagation()}>
    <button className="modal-close" onClick={onClose}><X/></button>
    <div className="agent-heading"><span className="eyebrow">APPLICATION AGENT</span><span className="agent-reviewed"><CheckCircle2 size={13}/>{locale==="en"?"Fact-checked · review before sending":"Проверено агентом · проверь перед отправкой"}</span></div>
    <h2>{decodeHtmlEntities(application.job.title)}</h2>
    <p className="muted">{decodeHtmlEntities(application.job.company)}</p>
    <div className="application-section-title"><h3>{t.tailoredSummary}</h3><span>{summaryWords} {locale==="en"?"words":"слов"}</span></div>
    <div className="copy-box">{application.tailored_summary}</div>
    <div className="application-section-title"><h3>{t.coverLetter}</h3><span>{coverWords} {locale==="en"?"words":"слов"}</span></div>
    <div className="copy-box letter">{application.cover_letter}</div>
    {application.recruiter_message&&<>
      <div className="application-section-title"><h3>{locale==="en"?"Recruiter message":"Сообщение рекрутеру"}</h3></div>
      <div className="copy-box">{application.recruiter_message}</div>
    </>}
    {!!application.interview_points?.length&&<>
      <div className="application-section-title"><h3>{locale==="en"?"Interview talking points":"Что подчеркнуть на интервью"}</h3></div>
      <div className="application-list">{application.interview_points.map(item=><span key={item}>✦ {item}</span>)}</div>
    </>}
    {!!application.caution_notes?.length&&<>
      <div className="application-section-title"><h3>{locale==="en"?"Do not overclaim":"Не преувеличивать"}</h3></div>
      <div className="caution-list">{application.caution_notes.map(item=><span key={item}>! {item}</span>)}</div>
    </>}
    <a className="primary-button link-button" href={application.job.url} target="_blank" rel="noreferrer">{t.openOriginal}<ArrowUpRight size={16}/></a>
  </div></div>;
}

function EmptyState({text}:{text:string}) {
  return <div className="empty-state"><Sparkles size={28}/><span>{text}</span></div>;
}

export default App;

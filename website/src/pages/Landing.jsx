import { useNavigate } from 'react-router-dom'
import {
  Shield, Brain, Target, Layers, ArrowRight, Activity,
  Lock, BarChart3, Cpu, Database, GitBranch, Eye, Zap,
  ChevronDown,
} from 'lucide-react'
import ShaderAnimation from '../components/ShaderAnimation'
import { GlassPrimaryButton, GlassGhostButton } from '../components/ui/LiquidGlassButton'
import { GlowCard } from '../components/ui/spotlight-card'

const features = [
  {
    icon: Brain,
    title: 'Hybrid ML Ensemble',
    desc: 'Four-model pipeline: LSTM Autoencoder for temporal anomalies, Isolation Forest for statistical outliers, Bi-LSTM with Attention for sequence modelling, and XGBoost for supervised classification — all scoring in parallel.',
  },
  {
    icon: Target,
    title: 'Contextual Risk Scoring',
    desc: 'Role-aware, time-aware, and activity-weighted scoring engine with alert persistence and cooldown to suppress fatigue. Admin and contractor activity carries elevated multipliers.',
  },
  {
    icon: Layers,
    title: 'MITRE ATT&CK Mapping',
    desc: 'Detected anomalies are mapped to MITRE ATT&CK tactics and techniques (e.g. TA0010 Exfiltration, TA0006 Credential Access) for standardized threat classification and triage.',
  },
  {
    icon: Eye,
    title: 'Behavioral Heatmaps',
    desc: 'Hourly behavioral fingerprints visualized per user. Spot anomalous access patterns at a glance across your entire organization.',
  },
  {
    icon: Lock,
    title: 'Analyst Feedback Loop',
    desc: 'Mark false positives and add investigation notes directly in the Forensics view. Feedback is recorded to a structured log for supervised retraining of the risk models.',
  },
  {
    icon: Zap,
    title: 'Real-Time Monitoring',
    desc: 'Live telemetry dashboard with 30-second auto-refresh. Critical alerts pulse for immediate attention and triage.',
  },
]

const pipelineSteps = [
  { icon: Database, label: 'Raw Telemetry', desc: 'Live agent captures mouse velocity, keystroke dynamics, and active window every 5 s. CERT r4.2 (logon, device, HTTP, email, file) used for model training.' },
  { icon: GitBranch, label: 'Feature Engineering', desc: 'Session aggregation, role encoding, time binning, activity frequency vectors, and behavioral baseline computation.' },
  { icon: Cpu, label: 'Hybrid Model Inference', desc: 'LSTM Autoencoder (temporal) + Isolation Forest (statistical) + Bi-LSTM with Attention (sequence) + XGBoost (supervised) — four models scoring in parallel.' },
  { icon: Activity, label: 'Risk Scoring', desc: 'Weighted multi-factor fusion with role multipliers (Admin 1.5×, Contractor 1.2×), after-hours amplification, and alert cooldown to suppress fatigue.' },
  { icon: BarChart3, label: 'Dashboard & Alerts', desc: 'Interactive charts, heatmaps, forensics timeline, MITRE ATT&CK tags, and analyst feedback tooling.' },
]

const metrics = [
  { value: '100', label: 'Max Risk Score', sub: 'Normalized 0–100 scale' },
  { value: '2,336', label: 'Total Events', sub: 'Ingested from live agent' },
  { value: '10', label: 'Users Monitored', sub: 'Pilot deployment · scalable' },
  { value: '< 30s', label: 'Detection Latency', sub: 'Avg agent-to-alert time' },
]

const techStack = [
  { name: 'Python', color: '#3776ab' },
  { name: 'PyTorch', color: '#ee4c2c' },
  { name: 'scikit-learn', color: '#f7931e' },
  { name: 'FastAPI', color: '#009688' },
  { name: 'React', color: '#61dafb' },
  { name: 'Tailwind CSS', color: '#06b6d4' },
  { name: 'Vite', color: '#646cff' },
  { name: 'Polars', color: '#cd792c' },
]

export default function Landing() {
  const navigate = useNavigate()

  return (
    <div className="relative min-h-screen text-on-surface">
      <ShaderAnimation />

      <div className="relative z-10">
        {/* ─── Hero ─── */}
        <section className="min-h-screen flex flex-col items-center justify-center text-center px-8 relative">
          <div className="bg-primary/10 backdrop-blur-sm rounded-3xl p-5 mb-8">
            <Shield size={48} className="text-primary" />
          </div>
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight max-w-4xl leading-tight drop-shadow-lg">
            UBA & Insider Threat{' '}
            <span className="bg-gradient-to-r from-primary to-primary-container bg-clip-text text-transparent">
              Detection
            </span>
          </h1>
          <p className="text-lg sm:text-xl text-on-surface-variant mt-6 max-w-2xl leading-relaxed drop-shadow-md">
            ML-Powered Security Analytics Platform. Behavioral baselines meet deep learning
            to catch what static rules can't.
          </p>
          <div className="flex items-center gap-4 mt-10">
            <GlassPrimaryButton
              onClick={() => navigate('/dashboard')}
              className="text-base px-8 py-3.5"
            >
              Launch Dashboard <ArrowRight size={18} />
            </GlassPrimaryButton>
            <GlassGhostButton
              onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}
              className="text-base px-6 py-3.5 backdrop-blur-sm"
            >
              Learn More
            </GlassGhostButton>
          </div>

          <div className="absolute bottom-12 flex flex-col items-center gap-2 animate-bounce">
            <span className="text-xs font-mono text-text-muted">Scroll</span>
            <ChevronDown size={18} className="text-text-muted" />
          </div>
        </section>

        <div className="h-32 bg-gradient-to-b from-transparent to-surface-base/95" />

        {/* ─── The Problem ─── */}
        <section className="py-28 px-8 bg-surface-base/95 backdrop-blur-md">
          <div className="max-w-4xl mx-auto text-center">
            <p className="text-xs font-mono text-tertiary uppercase tracking-[0.2em] mb-4">The Problem</p>
            <h2 className="text-3xl sm:text-4xl font-bold mb-6">
              Insider threats don't announce themselves.
            </h2>
            <p className="text-on-surface-variant text-lg leading-relaxed max-w-2xl mx-auto">
              Firewalls and signature-based SIEMs are built to stop outsiders. But when the threat comes from within —
              a compromised account, a disgruntled employee, or an over-privileged contractor —
              perimeter defenses are <span className="text-tertiary font-medium">completely blind</span>.
              Detecting insider threats requires understanding what normal looks like first.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-14">
              <GlowCard customSize glowColor="red" className="p-6">
                <p className="text-4xl font-bold font-mono text-error mb-2">68%</p>
                <p className="text-sm text-on-surface-variant">of organizations experienced at least one insider attack in the past 12 months (Ponemon 2022)</p>
              </GlowCard>
              <GlowCard customSize glowColor="orange" className="p-6">
                <p className="text-4xl font-bold font-mono text-tertiary mb-2">197 days</p>
                <p className="text-sm text-on-surface-variant">average time to identify and contain a data breach before it is discovered (IBM 2023)</p>
              </GlowCard>
              <GlowCard customSize glowColor="blue" className="p-6">
                <p className="text-4xl font-bold font-mono text-primary mb-2">3× harder</p>
                <p className="text-sm text-on-surface-variant">insider threats are 3× harder to detect than external attacks and far more likely to go unreported (Forrester)</p>
              </GlowCard>
            </div>
          </div>
        </section>

        {/* ─── Features ─── */}
        <section id="features" className="py-28 px-8 bg-surface-lowest/90 backdrop-blur-md">
          <div className="max-w-6xl mx-auto">
            <p className="text-xs font-mono text-primary uppercase tracking-[0.2em] text-center mb-4">Core Capabilities</p>
            <h2 className="text-3xl sm:text-4xl font-bold text-center mb-16">What makes this different.</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {features.map((f) => (
                <GlowCard key={f.title} customSize glowColor="blue" className="p-7 group">
                  <div className="bg-primary/10 rounded-xl p-3 inline-flex mb-5 group-hover:bg-primary/20 transition-colors">
                    <f.icon size={24} className="text-primary" />
                  </div>
                  <h3 className="text-lg font-semibold text-on-surface mb-2">{f.title}</h3>
                  <p className="text-sm text-on-surface-variant leading-relaxed">{f.desc}</p>
                </GlowCard>
              ))}
            </div>
          </div>
        </section>

        <div className="h-24 bg-gradient-to-b from-surface-lowest/90 via-transparent to-surface-base/95" />

        {/* ─── Pipeline ─── */}
        <section className="py-28 px-8 bg-surface-base/95 backdrop-blur-md">
          <div className="max-w-5xl mx-auto">
            <p className="text-xs font-mono text-primary uppercase tracking-[0.2em] text-center mb-4">Architecture</p>
            <h2 className="text-3xl sm:text-4xl font-bold text-center mb-16">End-to-end detection pipeline.</h2>
            <div className="space-y-1">
              {pipelineSteps.map((step, i) => (
                <div key={step.label} className="flex items-stretch gap-6">
                  <div className="flex flex-col items-center w-12 flex-shrink-0">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold font-mono flex-shrink-0 ${
                      i === pipelineSteps.length - 1 ? 'bg-primary/20 text-primary border-2 border-primary/40' : 'bg-surface-highest text-on-surface-variant'
                    }`}>{i + 1}</div>
                    {i < pipelineSteps.length - 1 && <div className="w-px flex-1 bg-outline-variant/30 my-1" />}
                  </div>
                  <div className="glass-card p-5 flex items-center gap-5 flex-1 mb-3">
                    <div className="bg-surface-highest rounded-lg p-3">
                      <step.icon size={20} className="text-primary" />
                    </div>
                    <div>
                      <h3 className="text-base font-semibold text-on-surface">{step.label}</h3>
                      <p className="text-sm text-on-surface-variant mt-0.5">{step.desc}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ─── Metrics ─── */}
        <section className="py-28 px-8 bg-surface-lowest/90 backdrop-blur-md">
          <div className="max-w-5xl mx-auto">
            <p className="text-xs font-mono text-primary uppercase tracking-[0.2em] text-center mb-4">Performance</p>
            <h2 className="text-3xl sm:text-4xl font-bold text-center mb-4">System at a glance.</h2>
            <p className="text-sm text-text-muted text-center mb-16 max-w-xl mx-auto">
              Currently running as a <span className="text-primary font-medium">10-user pilot</span>. The architecture is fully scalable — additional users and departments can be onboarded without changes to the detection pipeline.
            </p>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
              {metrics.map((m) => (
                <GlowCard key={m.label} customSize glowColor="purple" className="text-center p-8">
                  <p className="text-4xl sm:text-5xl font-bold font-mono bg-gradient-to-br from-primary to-primary-container bg-clip-text text-transparent mb-2">{m.value}</p>
                  <p className="text-sm font-semibold text-on-surface">{m.label}</p>
                  <p className="text-xs text-text-muted mt-1">{m.sub}</p>
                </GlowCard>
              ))}
            </div>
          </div>
        </section>

        <div className="h-24 bg-gradient-to-b from-surface-lowest/90 via-transparent to-transparent" />

        {/* ─── Tech Stack ─── */}
        <section className="py-28 px-8 bg-surface-base/90 backdrop-blur-md">
          <div className="max-w-4xl mx-auto text-center">
            <p className="text-xs font-mono text-primary uppercase tracking-[0.2em] mb-4">Technology</p>
            <h2 className="text-3xl sm:text-4xl font-bold mb-12">Built with modern tools.</h2>
            <div className="flex flex-wrap justify-center gap-4">
              {techStack.map((t) => (
                <div key={t.name} className="bg-surface-mid/80 backdrop-blur-sm px-6 py-3 rounded-xl text-sm font-mono font-medium text-on-surface border border-outline-variant/15 flex items-center gap-3 hover:border-primary/30 transition-colors">
                  <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: t.color }} />
                  {t.name}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ─── CTA ─── */}
        <section className="py-32 px-8 relative">
          <div className="absolute inset-0 bg-gradient-to-t from-surface-base/80 to-transparent pointer-events-none" />
          <div className="max-w-2xl mx-auto text-center relative z-10">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4 drop-shadow-lg">Ready to detect the invisible?</h2>
            <p className="text-on-surface-variant text-lg mb-10 drop-shadow-md">
              Explore the live dashboard and see the ML pipeline in action.
            </p>
            <GlassPrimaryButton
              onClick={() => navigate('/dashboard')}
              className="text-lg px-10 py-4 mx-auto"
            >
              Enter Security Operations <ArrowRight size={20} />
            </GlassPrimaryButton>
          </div>
        </section>

        {/* ─── Footer ─── */}
        <footer className="border-t border-outline-variant/10 py-10 px-8 bg-surface-base/95 backdrop-blur-md">
          <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Shield size={18} className="text-primary" />
              <span className="text-sm font-medium text-on-surface">UBA & Insider Threat Detection</span>
            </div>
            <p className="text-xs text-text-muted font-mono">Senior Design Project · CERT r4.2 Dataset · © 2026</p>
          </div>
        </footer>
      </div>
    </div>
  )
}

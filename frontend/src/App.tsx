import { useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { Bot, ChefHat, Clapperboard, Compass, LayoutDashboard, LineChart, Menu, PenSquare, PlaySquare, Settings as SettingsIcon, Target, Tv, X } from "lucide-react";
import Dashboard from "./pages/Dashboard";
import Niches from "./pages/Niches";
import Trends from "./pages/Trends";
import ContentStudio from "./pages/ContentStudio";
import VideoFactory from "./pages/VideoFactory";
import AgentControl from "./pages/AgentControl";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";
import Kitchen from "./pages/Kitchen";
import Channels from "./pages/Channels";
import Library from "./pages/Library";

export const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/nichos", label: "Niche Intelligence", icon: Target },
  { to: "/tendencias", label: "Trend Explorer", icon: Compass },
  { to: "/studio", label: "Content Studio", icon: PenSquare },
  { to: "/factory", label: "Video Factory", icon: Clapperboard },
  { to: "/videos", label: "Vídeos", icon: PlaySquare },
  { to: "/kitchen", label: "Reality Kitchen", icon: ChefHat },
  { to: "/canais", label: "Canais", icon: Tv },
  { to: "/agentes", label: "Agent Control", icon: Bot },
  { to: "/analytics", label: "Analytics", icon: LineChart },
  { to: "/config", label: "Settings", icon: SettingsIcon },
];

export default function App() {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-full">
      <aside className={`fixed inset-y-0 left-0 z-30 w-60 border-r border-line bg-panel transition-transform md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand font-bold">C</div>
          <div className="leading-tight">
            <div className="text-sm font-semibold">Creator Intelligence</div>
            <div className="text-xs text-muted">OS · v0.1</div>
          </div>
          <button className="ml-auto md:hidden" onClick={() => setOpen(false)} aria-label="Fechar menu"><X className="h-5 w-5" /></button>
        </div>
        <nav className="flex flex-col gap-1 px-3" aria-label="Navegação principal">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}
              className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${isActive ? "bg-brand/15 text-white ring-1 ring-brand/40" : "text-zinc-300 hover:bg-panel-2"}`}>
              <Icon className="h-4 w-4" /> {label}
            </NavLink>
          ))}
        </nav>
        <p className="absolute bottom-4 px-5 text-xs text-muted">Publicação sempre manual, com aprovação humana.</p>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col md:pl-60">
        <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-base/90 px-4 py-3 backdrop-blur md:hidden">
          <button onClick={() => setOpen(true)} aria-label="Abrir menu"><Menu className="h-5 w-5" /></button>
          <span className="text-sm font-semibold">Creator Intelligence OS</span>
        </div>
        <main className="mx-auto w-full max-w-7xl flex-1 p-4 md:p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/nichos" element={<Niches />} />
            <Route path="/tendencias" element={<Trends />} />
            <Route path="/studio" element={<ContentStudio />} />
            <Route path="/factory" element={<VideoFactory />} />
            <Route path="/videos" element={<Library />} />
            <Route path="/kitchen" element={<Kitchen />} />
            <Route path="/canais" element={<Channels />} />
            <Route path="/agentes" element={<AgentControl />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/config" element={<Settings />} />
            <Route path="*" element={<p className="text-muted">Página não encontrada.</p>} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Wand2 } from "lucide-react";
import { api, fmtDate, post, useApi, type Script } from "../api";
import { ScriptEditor } from "../components/Review";
import { Async, Badge, Button, Card, Empty, Notice, PageHeader, StatusBadge, inputCls } from "../components/ui";

interface Channel { id: string; name: string; focus: string; workflows: string[]; default_niche: string }

const NICHES: [string, string][] = [
  ["natureza_animais", "Natureza e animais"], ["ciencia_espaco", "Ciência e espaço"], ["documentarios_misterios", "Curiosidades e mistérios"],
  ["historias", "Histórias"], ["tecnologia_ia", "Tecnologia e IA"], ["psicologia", "Psicologia"], ["financas_pessoais", "Finanças pessoais"],
  ["negocios", "Negócios"], ["games", "Games"], ["tutoriais_software", "Tutoriais"],
];

function NewShort({ onCreated }: { onCreated: () => void }) {
  const [params] = useSearchParams();
  const channels = useApi<Channel[]>("/channels");
  const videoChannels = (channels.data ?? []).filter((c) => c.workflows.includes("video"));
  const [channel, setChannel] = useState("natureza");
  const [topic, setTopic] = useState(params.get("topic") ?? "");
  const [niche, setNiche] = useState("natureza_animais");
  const [tone, setTone] = useState("educativo");
  const [suggestions, setSuggestions] = useState<{ title: string }[]>([]);
  const [msg, setMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (topic.trim().length < 3) return setSuggestions([]);
    const id = setTimeout(() => api<{ title: string }[]>(`/topics/search?q=${encodeURIComponent(topic)}`).then(setSuggestions).catch(() => setSuggestions([])), 350);
    return () => clearTimeout(id);
  }, [topic]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await post("/videos", { topic, channel_id: channel, niche_id: niche, tone, format: "short", language: "pt" });
      setMsg({ kind: "success", text: "Workflow criado: pesquisa → briefing → roteiro → revisão. O roteiro aparece abaixo em instantes e aguarda sua aprovação." });
      onCreated();
    } catch (err) {
      setMsg({ kind: "error", text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Novo Short (pt-BR, vertical, até 60s, sempre legendado)">
      <form onSubmit={submit} className="grid gap-3 md:grid-cols-5">
        <div>
          <label className="mb-1 block text-xs text-muted" htmlFor="channel">Canal</label>
          <select id="channel" className={inputCls} value={channel} onChange={(e) => setChannel(e.target.value)}>
            {videoChannels.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className="relative md:col-span-2">
          <label className="mb-1 block text-xs text-muted" htmlFor="topic">Tema (artigo da Wikipedia pt)</label>
          <input id="topic" className={inputCls} value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Ex.: Polvo, Axolote, Bicho-preguiça" required minLength={2} autoComplete="off" />
          {suggestions.length > 0 && !suggestions.some((s) => s.title === topic) && (
            <ul className="absolute z-10 mt-1 w-full rounded-lg border border-line bg-panel-2 text-sm shadow-xl">
              {suggestions.map((s) => <li key={s.title}><button type="button" className="w-full px-3 py-1.5 text-left hover:bg-panel" onClick={() => setTopic(s.title)}>{s.title}</button></li>)}
            </ul>
          )}
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted" htmlFor="niche">Nicho</label>
          <select id="niche" className={inputCls} value={niche} onChange={(e) => setNiche(e.target.value)}>{NICHES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted" htmlFor="tone">Tom</label>
          <select id="tone" className={inputCls} value={tone} onChange={(e) => setTone(e.target.value)}>
            <option value="educativo">Educativo</option><option value="comico">Cômico</option><option value="criativo">Criativo</option>
          </select>
        </div>
        <div className="flex items-center gap-3 md:col-span-5">
          <Button type="submit" disabled={busy}><Wand2 className="h-4 w-4" /> {busy ? "Criando…" : "Gerar roteiro"}</Button>
          <span className="text-xs text-muted">Vídeos do Clip+ (restaurantes) são criados na página Reality Kitchen.</span>
        </div>
      </form>
      {msg && <div className="mt-3"><Notice kind={msg.kind}>{msg.text}</Notice></div>}
    </Card>
  );
}

export default function ContentStudio() {
  const scripts = useApi<Script[]>("/scripts", 6000);
  const calendar = useApi<{ script_id: string; title: string; date: string; status: string }[]>("/calendar");
  const [params] = useSearchParams();
  const [selected, setSelected] = useState<string | null>(params.get("script"));
  return (
    <>
      <PageHeader title="Content Studio" subtitle="Briefings, roteiros, títulos, descrições, capas e calendário. Tudo editável antes de aprovar." />
      <div className="space-y-6">
        <NewShort onCreated={scripts.reload} />
        <div className="grid gap-6 lg:grid-cols-3">
          <Card title="Roteiros">
            <Async q={scripts}>
              {(list) => list.length === 0 ? <Empty>Nenhum roteiro ainda.</Empty> : (
                <ul className="space-y-1">
                  {list.map((s) => (
                    <li key={s.id}><button onClick={() => setSelected(s.id)} className={`w-full rounded-lg p-2 text-left text-sm hover:bg-panel-2 ${selected === s.id ? "bg-panel-2 ring-1 ring-accent/50" : ""}`}>
                      <div className="font-medium">{s.title}</div>
                      <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted"><StatusBadge status={s.status} />{s.channel_id && <Badge>{s.channel_id === "clips_plus" ? "Clip+" : "Clip+ Nat"}</Badge>} {fmtDate(s.created_at)}</div>
                    </button></li>
                  ))}
                </ul>
              )}
            </Async>
            <h3 className="mb-2 mt-6 text-xs font-semibold uppercase text-muted">Calendário editorial</h3>
            {calendar.data?.length ? (
              <ul className="space-y-1 text-sm">{[...calendar.data].sort((a, b) => a.date.localeCompare(b.date)).map((c) => <li key={c.script_id} className="flex gap-2"><span className="text-muted">{c.date}</span><span className="truncate">{c.title}</span></li>)}</ul>
            ) : <p className="text-xs text-muted">Defina uma data planejada em um roteiro.</p>}
          </Card>
          <Card title="Editor" className="lg:col-span-2">
            {selected ? <ScriptEditor key={selected} id={selected} onSaved={() => { scripts.reload(); calendar.reload(); }} /> : <Empty>Selecione um roteiro.</Empty>}
          </Card>
        </div>
      </div>
    </>
  );
}

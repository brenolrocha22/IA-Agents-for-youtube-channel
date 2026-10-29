import { useState } from "react";
import { Check, Film, RefreshCw, Search, Upload, X } from "lucide-react";
import { mediaUrl, post, useApi } from "../api";
import { Async, Badge, Bar, Button, Notice, inputCls } from "./ui";

export interface Candidate {
  id: string; provider: string; title: string; page_url: string; author: string; license: string; license_url: string | null;
  license_status: "aceita" | "condicional" | "rejeitada"; license_note: string; attribution_required: boolean;
  width: number | null; height: number | null; duration: number | null; local_path: string | null; preview_path: string | null;
  metadata_score: number; matched_terms: string[]; credit: string;
}
export interface VScene {
  index: number; narration: string; action: string; queries: string[]; start: number | null; end: number | null;
  candidates: Candidate[]; selected_id: string | null; clip_start: number | null;
  validation: "pendente" | "revisao" | "validada" | "rejeitada"; validated_by: string | null; validation_method: string | null; note: string;
  adaptation: string | null;
}
interface PlanResp { plan: { id: string; subject_en: string; providers: string[]; scenes: VScene[]; log: string[] }; coverage: number; manual_licenses?: string[] }

const LICENSES = ["Pexels License", "Pixabay Content License", "CC0", "Public domain", "CC BY 4.0", "CC BY 3.0", "CC BY 2.0", "CC BY-SA 4.0", "Autorização do autor"];

/** Filmagem baixada pelo proprietário (ex.: site do Pexels), com origem e licença declaradas. */
function UploadForm({ planId, index, hasSelected, onDone }: { planId: string; index: number; hasSelected: boolean; onDone: (r: PlanResp) => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [license, setLicense] = useState(LICENSES[0]);
  if (!open) return <Button variant="ghost" onClick={() => setOpen(true)}><Upload className="h-4 w-4" /> Enviar filmagem licenciada</Button>;
  return (
    <form className="space-y-2 rounded-lg border border-line p-3" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true);
      setErr(null);
      try {
        onDone(await post<PlanResp>(`/visual/plans/${planId}/scenes/${index}/upload`, new FormData(e.currentTarget)));
        setOpen(false);
      } catch (ex) { setErr(ex instanceof Error ? ex.message : String(ex)); }
      finally { setBusy(false); }
    }}>
      <p className="text-xs text-muted">Baixe o vídeo você mesmo no site (ex.: Pexels → Download grátis) e informe a origem. O sistema registra a licença, gera os créditos e mostra os quadros para validação.</p>
      <input name="file" type="file" accept="video/*" required className="block w-full text-xs" />
      <input name="page_url" type="url" required placeholder="Link da página do vídeo (ex.: https://www.pexels.com/pt-br/video/...)" className={inputCls} />
      <div className="grid gap-2 sm:grid-cols-2">
        <input name="author" required minLength={2} placeholder="Autor/criador" className={inputCls} />
        <select name="license" value={license} onChange={(e) => setLicense(e.target.value)} className={inputCls}>{LICENSES.map((l) => <option key={l}>{l}</option>)}</select>
      </div>
      <input name="title" placeholder="Título (opcional)" className={inputCls} />
      <textarea name="note" placeholder={license === "Autorização do autor" ? "Obrigatório: quem autorizou, quando, escopo (uso comercial e edição)" : "Observações (opcional)"}
        required={license === "Autorização do autor"} className={`${inputCls} min-h-14`} />
      {hasSelected && <label className="flex items-center gap-2 text-xs"><input type="checkbox" name="as_shot" value="true" /> Usar como tomada extra (mantém a filmagem atual e adiciona um corte)</label>}
      {err && <Notice kind="error">{err}</Notice>}
      <div className="flex gap-2"><Button type="submit" variant="secondary" disabled={busy}>{busy ? "Enviando…" : "Enviar"}</Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>Cancelar</Button></div>
    </form>
  );
}

const VAL: Record<string, ["green" | "yellow" | "red" | "gray", string]> = {
  validada: ["green", "validada"], revisao: ["yellow", "aguardando validação visual"], pendente: ["red", "pendente"], rejeitada: ["red", "rejeitada"],
};
const LIC: Record<string, "green" | "yellow" | "red"> = { aceita: "green", condicional: "yellow", rejeitada: "red" };
const fmt = (t: number | null) => (t === null ? "—" : `${t.toFixed(1)}s`);

function SceneCard({ planId, s, onChange }: { planId: string; s: VScene; onChange: (r: PlanResp) => void }) {
  const [q, setQ] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const sel = s.candidates.find((c) => c.id === s.selected_id);
  const [v0, label] = VAL[s.validation];
  const act = async (path: string, body: unknown) => {
    setBusy(true);
    try { onChange(await post<PlanResp>(`/visual/plans/${planId}/scenes/${s.index}/${path}`, body)); setMsg(null); }
    catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  return (
    <li id={`field-scene-${s.index}`} className="rounded-lg border border-line bg-panel-2/40 p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <Badge color="blue">Cena {s.index + 1}</Badge><span className="text-muted">{fmt(s.start)} → {fmt(s.end)}</span>
        <Badge color={v0}>{label}</Badge><span className="text-muted">ação exigida: <b className="text-zinc-200">{s.action || "assunto"}</b></span>
      </div>
      <div className="grid gap-3 lg:grid-cols-[1fr_1.2fr]">
        <div className="space-y-2 text-sm">
          <p className="rounded bg-black/30 p-2">“{s.narration}”</p>
          {s.note && <p className="text-xs text-muted">{s.note}</p>}
          {s.validated_by && <p className="text-xs text-emerald-300">Validada por {s.validated_by} — {s.validation_method}</p>}
          {msg && <Notice kind="error">{msg}</Notice>}
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" disabled={busy || !sel} onClick={() => act("validate", { status: "validada" })}><Check className="h-4 w-4" /> Mostra a ação</Button>
            <Button variant="danger" disabled={busy || !sel} onClick={() => act("validate", { status: "rejeitada", note: "Material não mostra a ação narrada" })}><X className="h-4 w-4" /> Não mostra</Button>
          </div>
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) act("search", { query: q }); }}>
            <input className={inputCls} placeholder="Nova busca (inglês), ex.: octopus ink cloud" value={q} onChange={(e) => setQ(e.target.value)} />
            <Button type="submit" variant="ghost" disabled={busy}><Search className="h-4 w-4" /></Button>
          </form>
          <UploadForm planId={planId} index={s.index} hasSelected={!!sel} onDone={onChange} />
        </div>
        <div className="space-y-2">
          {sel ? (
            <>
              {sel.local_path && (
                <video controls muted preload="metadata" className="max-h-56 w-full rounded border border-line bg-black"
                  src={`${mediaUrl(sel.local_path)}#t=${s.clip_start ?? 0}`} />
              )}
              {sel.preview_path && <img src={mediaUrl(sel.preview_path)} alt="Quadros amostrados" className="w-full rounded border border-line" />}
              <div className="text-xs">
                <a className="text-accent hover:underline" href={sel.page_url} target="_blank" rel="noreferrer">{sel.title}</a> · {sel.provider} · {sel.author}
                <div className="mt-1 flex flex-wrap gap-1">
                  <Badge color={LIC[sel.license_status]}>{sel.license}</Badge>
                  {sel.attribution_required && <Badge>crédito obrigatório</Badge>}
                  <Badge>{sel.width}x{sel.height} · {sel.duration?.toFixed(0)}s</Badge>
                  <Badge color="gray">metadados: {sel.matched_terms.join(", ") || "—"}</Badge>
                </div>
                {sel.license_note && <p className="mt-1 text-muted">{sel.license_note}</p>}
              </div>
            </>
          ) : <div className="flex h-32 items-center justify-center rounded border border-dashed border-red-500/50 text-sm text-red-300"><Film className="mr-2 h-4 w-4" /> Sem filmagem: cena não coberta</div>}
          {s.candidates.length > 1 && (
            <select aria-label="Trocar material" className={`${inputCls} py-1 text-xs`} value="" disabled={busy}
              onChange={(e) => e.target.value && act("select", { candidate_id: e.target.value })}>
              <option value="">Trocar material ({s.candidates.length} candidatos)…</option>
              {s.candidates.filter((c) => c.id !== s.selected_id).map((c) => (
                <option key={c.id} value={c.id}>[{c.license_status}] {c.title.slice(0, 60)} — {c.license} ({c.matched_terms.join(", ") || "genérico"})</option>
              ))}
            </select>
          )}
        </div>
      </div>
      {s.adaptation && (
        <div className="mt-3 rounded border border-amber-500/40 bg-amber-500/10 p-2 text-sm">
          <b>Adaptação factual proposta</b> (só entra no vídeo se você aprovar): “{s.adaptation}”
        </div>
      )}
    </li>
  );
}

/** Mapa NARRAÇÃO → VÍDEO SELECIONADO com indicador de cobertura visual. */
export default function VisualPlanPanel({ planId }: { planId: string }) {
  const q = useApi<PlanResp>(`/visual/plans/${planId}`);
  const [data, setData] = useState<PlanResp | null>(null);
  const d = data ?? q.data;
  return (
    <Async q={q}>
      {() => !d ? null : (
        <div id="field-visual" className="space-y-3 rounded-lg">
          <div className="rounded-lg border border-line p-3">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">COBERTURA VISUAL DO ROTEIRO: {Math.round(d.coverage * 100)}%</span>
              <Badge color={d.coverage >= 0.999 ? "green" : "red"}>{d.coverage >= 0.999 ? "completa" : "incompleta — vídeo não pode ser aprovado"}</Badge>
              <span className="ml-auto text-xs text-muted">Fontes: {d.plan.providers.join(", ")}</span>
              <Button variant="ghost" onClick={() => { setData(null); q.reload(); }}><RefreshCw className="h-4 w-4" /></Button>
            </div>
            <Bar value={d.coverage * 100} color={d.coverage >= 0.999 ? "bg-emerald-500" : "bg-brand"} />
            <p className="mt-2 text-xs text-muted">Mede o tempo narrado coberto por filmagens validadas que mostram a ação. A correspondência automática usa
              apenas metadados (título/descrição); a confirmação visual é sua, olhando os quadros amostrados ou o vídeo.</p>
          </div>
          <ul className="space-y-3">{d.plan.scenes.map((s) => <SceneCard key={s.index} planId={d.plan.id} s={s} onChange={setData} />)}</ul>
        </div>
      )}
    </Async>
  );
}

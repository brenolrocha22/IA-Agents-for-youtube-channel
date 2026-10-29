import { useState } from "react";
import { Copy } from "lucide-react";
import { useApi } from "../api";
import { Async, Badge, Button } from "./ui";

interface Seo {
  titles: string[]; description: string; hashtags: string[]; tags: string[]; pinned_comment: string; credits: string;
  hook_suggestion: string; youtube_description: string; notes: string[]; copy_ready: string;
}

function CopyBox({ label, text, rows = 3 }: { label: string; text: string; rows?: number }) {
  const [ok, setOk] = useState(false);
  return (
    <div>
      <div className="mb-1 flex items-center gap-2 text-xs text-muted">{label}
        <button type="button" className="ml-auto inline-flex items-center gap-1 text-accent hover:underline"
          onClick={() => navigator.clipboard.writeText(text).then(() => { setOk(true); setTimeout(() => setOk(false), 1500); })}>
          <Copy className="h-3 w-3" /> {ok ? "copiado!" : "copiar"}
        </button>
      </div>
      <textarea readOnly rows={rows} value={text} className="w-full rounded-lg border border-line bg-black/30 p-2 text-xs" />
    </div>
  );
}

/** YouTube SEO Agent: textos prontos para colar no YouTube Studio. A escolha final é do proprietário. */
export default function SeoPanel({ scriptId }: { scriptId: string }) {
  const q = useApi<Seo>(`/visual/seo/${scriptId}`);
  return (
    <Async q={q}>
      {(s) => (
        <div className="space-y-3">
          <div className="space-y-1">
            <div className="text-xs text-muted">Títulos sugeridos (até 100 caracteres, só com o que o vídeo mostra)</div>
            {s.titles.map((t) => <CopyBox key={t} label={`${t.length} caracteres`} text={t} rows={1} />)}
          </div>
          <CopyBox label="Descrição completa para o YouTube (com créditos em seção separada)" text={s.youtube_description} rows={10} />
          <div className="flex flex-wrap gap-1">{s.hashtags.map((h) => <Badge key={h} color="blue">{h}</Badge>)}</div>
          <CopyBox label="Tags (campo 'Tags' do YouTube Studio)" text={s.tags.join(", ")} rows={2} />
          <CopyBox label="Comentário fixado" text={s.pinned_comment} rows={2} />
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-xs"><b>Gancho:</b> {s.hook_suggestion}</div>
          {s.notes.map((n) => <p key={n} className="text-xs text-muted">{n}</p>)}
          <Button variant="ghost" onClick={() => navigator.clipboard.writeText(s.copy_ready)}><Copy className="h-4 w-4" /> Copiar tudo</Button>
        </div>
      )}
    </Async>
  );
}

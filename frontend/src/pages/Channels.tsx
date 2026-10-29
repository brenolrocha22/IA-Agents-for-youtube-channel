import { useState } from "react";
import { Palette } from "lucide-react";
import { mediaUrl, post, useApi } from "../api";
import { Async, Badge, Button, Card, Empty, Notice, PageHeader } from "../components/ui";

interface Channel {
  id: string; name: string; name_pending: boolean; focus: string; tagline: string; hashtags: string[];
  palette: Record<string, number[]>; branding: Record<string, string>;
}

const LABEL: Record<string, string> = {
  avatar_800x800: "Foto do perfil (800x800)", banner_2560x1440: "Banner (2560x1440)", capa_modelo_1080x1920: "Capa de Short (padrão / curiosidades)",
  capa_modelo_vida_selvagem_1080x1920: "Capa — vida selvagem", capa_modelo_cinematografica_1080x1920: "Capa — natureza cinematográfica",
};
const order = (keys: string[]) => ["avatar_800x800", "banner_2560x1440", ...keys.filter((k) => k.startsWith("capa_modelo")).sort()].filter((k) => keys.includes(k));

export default function Channels() {
  const q = useApi<Channel[]>("/channels");
  const [msg, setMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [stamp, setStamp] = useState(0);

  async function generate(id: string) {
    try {
      await post(`/channels/${id}/branding`);
      setStamp(Date.now());
      setMsg({ kind: "success", text: "Identidade visual gerada em output/branding/. Envie as imagens no YouTube Studio → Personalização." });
      q.reload();
    } catch (e) {
      setMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  }

  return (
    <>
      <PageHeader title="Canais" subtitle="Identidade visual original de cada canal. As imagens são enviadas por você no YouTube Studio; o sistema não acessa sua conta." />
      {msg && <div className="mb-4"><Notice kind={msg.kind}>{msg.text}</Notice></div>}
      <Async q={q}>
        {(chs) => (
          <div className="space-y-6">
            {chs.map((c) => (
              <Card key={c.id} title={c.name} actions={<Button onClick={() => generate(c.id)}><Palette className="h-4 w-4" /> {Object.keys(c.branding).length ? "Gerar novamente" : "Gerar identidade visual"}</Button>}>
                <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
                  {c.name_pending && <Badge color="yellow">nome provisório</Badge>}
                  <span className="text-zinc-300">{c.focus}</span>
                </div>
                <p className="mb-2 text-sm">Slogan: <b>{c.tagline}</b> · {c.hashtags.join(" ")}</p>
                <div className="mb-4 flex gap-2">{Object.entries(c.palette).map(([k, v]) => <span key={k} title={k} className="h-6 w-10 rounded border border-line" style={{ background: `rgb(${v.join(",")})` }} />)}</div>
                {Object.keys(c.branding).length === 0 ? <Empty>Ainda não gerada.</Empty> : (
                  <div className="grid grid-cols-2 gap-4 md:grid-cols-[200px_1fr] xl:grid-cols-[200px_1fr_repeat(3,140px)]">
                    {order(Object.keys(c.branding)).map((k) => (
                      <figure key={k} className={k.startsWith("banner") ? "col-span-2 md:col-span-1" : ""}>
                        <a href={mediaUrl(c.branding[k])} target="_blank" rel="noreferrer">
                          <img key={stamp} src={mediaUrl(c.branding[k])} alt={LABEL[k]} className={`w-full rounded-lg border border-line ${k.startsWith("avatar") ? "rounded-full" : ""}`} />
                        </a>
                        <figcaption className="mt-1 text-xs text-muted">{LABEL[k]}</figcaption>
                      </figure>
                    ))}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </Async>
    </>
  );
}

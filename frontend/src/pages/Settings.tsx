import { useApi } from "../api";
import { Async, Badge, Card, PageHeader } from "../components/ui";

interface SettingsData {
  env: { name: string; configured: boolean; secret: boolean; used_by: string; value?: string }[];
  policy: { auto_allowed: string[]; requires_human_approval: string[]; allowed_subprocesses: string[]; allowed_write_dirs: string[]; limits: Record<string, number> };
  providers: { name: string; status: string; detail: string }[];
  production: Record<string, string>;
  scoring: { weights: Record<string, number> };
}

const STATUS_COLOR: Record<string, "green" | "gray" | "red" | "yellow"> = { ativo: "green", desativado: "gray", "indisponível": "yellow", erro: "red" };

export default function Settings() {
  const q = useApi<SettingsData>("/settings");
  return (
    <>
      <PageHeader title="Settings" subtitle="Somente leitura na interface. Edite .env e config/*.json e reinicie o servidor." />
      <Async q={q}>
        {(s) => (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Provedores e integrações">
              <ul className="divide-y divide-line text-sm">{s.providers.map((p) => (
                <li key={p.name} className="flex flex-wrap items-center gap-2 py-2"><span className="flex-1">{p.name}</span><Badge color={STATUS_COLOR[p.status] ?? "gray"}>{p.status}</Badge>
                  <p className="w-full text-xs text-muted">{p.detail}</p></li>
              ))}</ul>
            </Card>
            <Card title="Variáveis de ambiente">
              <ul className="divide-y divide-line text-sm">{s.env.map((e) => (
                <li key={e.name} className="flex flex-wrap items-center gap-2 py-2">
                  <code className="flex-1 text-xs">{e.name}</code>
                  {e.secret && <Badge color="blue">segredo</Badge>}
                  <Badge color={e.configured ? "green" : "gray"}>{e.configured ? "configurada" : "ausente"}</Badge>
                  <p className="w-full text-xs text-muted">{e.used_by}{e.value ? ` · ${e.value}` : ""}</p>
                </li>
              ))}</ul>
              <p className="mt-2 text-xs text-muted">Valores de segredos nunca são exibidos.</p>
            </Card>
            <Card title="Limites de execução">
              <dl className="grid grid-cols-2 gap-2 text-sm">{Object.entries(s.policy.limits).map(([k, v]) => <div key={k}><dt className="text-xs text-muted">{k}</dt><dd className="font-semibold">{v}</dd></div>)}</dl>
            </Card>
            <Card title="Permissões">
              <h3 className="text-xs font-semibold uppercase text-muted">Automático (baixo risco)</h3>
              <div className="mt-1 flex flex-wrap gap-1">{s.policy.auto_allowed.map((a) => <Badge key={a} color="green">{a}</Badge>)}</div>
              <h3 className="mt-3 text-xs font-semibold uppercase text-muted">Exige aprovação humana</h3>
              <div className="mt-1 flex flex-wrap gap-1">{s.policy.requires_human_approval.map((a) => <Badge key={a} color="red">{a}</Badge>)}</div>
              <p className="mt-3 text-xs text-muted">Subprocessos permitidos: {s.policy.allowed_subprocesses.join(", ")} · Escrita: {s.policy.allowed_write_dirs.join(", ")}</p>
            </Card>
            <Card title="Configuração de produção">
              <dl className="space-y-1 text-sm">{Object.entries(s.production).map(([k, v]) => <div key={k}><dt className="inline text-muted">{k}: </dt><dd className="inline">{v}</dd></div>)}</dl>
            </Card>
            <Card title="Pesos do ranking de nichos">
              <dl className="grid grid-cols-2 gap-1 text-sm">{Object.entries(s.scoring.weights).map(([k, v]) => <div key={k}>{k}: <b>{Math.round(v * 100)}%</b></div>)}</dl>
            </Card>
          </div>
        )}
      </Async>
    </>
  );
}

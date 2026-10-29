import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App, { NAV } from "./App";

function mockFetch(handler: (url: string) => unknown, status = 200) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(handler(url)), { status, headers: { "Content-Type": "application/json" } })));
}

afterEach(() => vi.unstubAllGlobals());

const DASH = {
  projects: [], project_count: 0, tasks_by_status: { pending: 0, running: 0, completed: 0, failed: 0, cancelled: 0, awaiting_approval: 0 },
  active_tasks: [], videos_rendered: 0, videos_failed: 0, errors: [], cost_estimated_usd: 0, tokens_estimated: 0, api_calls: 0,
  top_niches: [], niche_report_date: null, opportunities: [], trend_date: null,
};

test("sidebar lista todas as páginas obrigatórias", () => {
  mockFetch(() => DASH);
  render(<MemoryRouter><App /></MemoryRouter>);
  for (const item of NAV) expect(screen.getAllByText(item.label).length).toBeGreaterThan(0);
});

test("dashboard mostra estados vazios a partir da API", async () => {
  mockFetch((url) => (url.includes("/kitchen") ? { counts: {} } : url.includes("/tasks") ? [] : DASH));
  render(<MemoryRouter><App /></MemoryRouter>);
  expect(await screen.findByText("Nenhuma pesquisa executada.", { exact: false })).toBeInTheDocument();
  expect(await screen.findByText("Nenhuma aprovação pendente.")).toBeInTheDocument();
});

test("tarefa pendente no dashboard vira link para a revisão daquela tarefa", async () => {
  const dash = { ...DASH, tasks_by_status: { ...DASH.tasks_by_status, awaiting_approval: 1 },
    active_tasks: [{ id: "task_abc", type: "final_approval", agent: "orchestrator", status: "awaiting_approval" }] };
  mockFetch((url) => (url.includes("/kitchen") ? { counts: {} } : url.includes("/tasks") || url.includes("/workflows") ? [] : dash));
  render(<MemoryRouter><App /></MemoryRouter>);
  const link = await screen.findByRole("link", { name: /Tarefas em andamento/ });
  expect(link).toHaveAttribute("href", "/factory?task=task_abc");
  expect(link).toHaveTextContent("Assistir e aprovar vídeo");
});

test("sem pendências o card não é clicável", async () => {
  mockFetch((url) => (url.includes("/kitchen") ? { counts: {} } : url.includes("/tasks") ? [] : DASH));
  render(<MemoryRouter><App /></MemoryRouter>);
  await screen.findByText("Tarefas em andamento");
  expect(screen.queryByRole("link", { name: /Tarefas em andamento/ })).toBeNull();
});

test("exibe estado de erro quando a API falha", async () => {
  mockFetch(() => ({ detail: "backend fora do ar" }), 500);
  render(<MemoryRouter><App /></MemoryRouter>);
  await waitFor(() => expect(screen.getAllByRole("alert")[0]).toHaveTextContent("backend fora do ar"));
});

test("analytics sem dados reais não inventa métricas", async () => {
  mockFetch((url) => (url.includes("/published") ? []
    : { report: { demo: false, records: 0, totals: {}, comparisons: {}, recommendations: [], limitations: [] }, records: [] }));
  render(<MemoryRouter initialEntries={["/analytics"]}><App /></MemoryRouter>);
  expect(await screen.findByText(/Nenhuma métrica real importada/)).toBeInTheDocument();
});

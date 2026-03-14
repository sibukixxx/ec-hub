import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { RoutableProps } from 'preact-router';
import { useEffect, useState } from 'preact/hooks';
import { api } from '../api';
import { Alerts } from '../components/Alerts';
import { Badge } from '../components/Badge';
import { healthBadge, runStatusBadge } from '../lib/color';
import { formatTimestamp, inputValue } from '../lib/format';
import { queryKeys } from '../lib/query-keys';
import type {
  JobRun,
  ListingLimits,
  ResearchRun,
  SchedulerStatus,
  ServiceHealth,
} from '../types';

function parseKeywords(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((keyword) => keyword.trim())
    .filter(Boolean);
}

function mergeRun(runs: ResearchRun[], nextRun: ResearchRun): ResearchRun[] {
  const existing = runs.find((run) => run.id === nextRun.id);
  if (!existing) {
    return [nextRun, ...runs].slice(0, 10);
  }
  return runs.map((run) => (run.id === nextRun.id ? nextRun : run));
}

export function Operations(_props: RoutableProps) {
  const [keywords, setKeywords] = useState('');
  const [pages, setPages] = useState(1);
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const runsQuery = useQuery<ResearchRun[]>({
    queryKey: queryKeys.researchRuns,
    queryFn: () => api.getResearchRuns(10),
  });

  const limitsQuery = useQuery<ListingLimits>({
    queryKey: queryKeys.listingLimits,
    queryFn: () => api.getListingLimits(),
  });

  const jobRunsQuery = useQuery<JobRun[]>({
    queryKey: queryKeys.jobRuns,
    queryFn: () => api.getJobRuns(null, 5),
  });

  const healthQuery = useQuery<ServiceHealth[]>({
    queryKey: queryKeys.systemHealth,
    queryFn: () => api.getSystemHealth(),
  });

  const schedulerQuery = useQuery<SchedulerStatus>({
    queryKey: queryKeys.schedulerStatus,
    queryFn: () => api.getSchedulerStatus(),
  });

  const activeRunQuery = useQuery<ResearchRun>({
    queryKey: queryKeys.researchRun(activeRunId!),
    queryFn: () => api.getResearchRun(activeRunId!),
    enabled: activeRunId !== null,
    refetchInterval: 2500,
  });

  // Detect initial active run from loaded runs
  useEffect(() => {
    if (runsQuery.data && activeRunId === null) {
      const running = runsQuery.data.find((run) => !run.completed_at);
      if (running) setActiveRunId(running.id);
    }
  }, [runsQuery.data, activeRunId]);

  // Merge polled active run into runs list & detect completion
  useEffect(() => {
    if (!activeRunQuery.data) return;
    const run = activeRunQuery.data;

    queryClient.setQueryData<ResearchRun[]>(queryKeys.researchRuns, (old) =>
      old ? mergeRun(old, run) : [run]
    );

    if (run.completed_at) {
      setActiveRunId(null);
      setNotice(
        `Research run #${run.id} completed with ${run.candidates_found || 0} candidates.`
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobRuns });
      void queryClient.invalidateQueries({ queryKey: queryKeys.systemHealth });
    }
  }, [activeRunQuery.data, queryClient]);

  const researchMutation = useMutation({
    mutationFn: (payload: { pages: number; keywords?: string[] }) =>
      api.runResearch(payload),
    onMutate: () => {
      setError(null);
      setNotice(null);
    },
    onSuccess: async (result) => {
      setNotice(`Research run #${result.run_id} started.`);
      setActiveRunId(result.run_id);
      void queryClient.invalidateQueries({ queryKey: queryKeys.researchRuns });
    },
    onError: (e: Error) => setError(e.message),
  });

  const listingMutation = useMutation({
    mutationFn: () => api.runListing(),
    onMutate: () => {
      setError(null);
      setNotice(null);
    },
    onSuccess: (result) => {
      setNotice(
        `Listing run completed: ${result.listed_count} listings published.`
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.listingLimits });
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobRuns });
    },
    onError: (e: Error) => setError(e.message),
  });

  const ordersMutation = useMutation({
    mutationFn: () => api.checkOrders(),
    onMutate: () => {
      setError(null);
      setNotice(null);
    },
    onSuccess: (result) => {
      setNotice(
        `Order sync completed: ${result.new_orders} new orders registered.`
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobRuns });
    },
    onError: (e: Error) => setError(e.message),
  });

  const startResearch = () => {
    const payload: { pages: number; keywords?: string[] } = { pages };
    const parsedKeywords = parseKeywords(keywords);
    if (parsedKeywords.length > 0) {
      payload.keywords = parsedKeywords;
    }
    researchMutation.mutate(payload);
  };

  const loading =
    runsQuery.isLoading ||
    limitsQuery.isLoading ||
    jobRunsQuery.isLoading ||
    healthQuery.isLoading ||
    schedulerQuery.isLoading;

  const runs = runsQuery.data ?? [];
  const listingLimits = limitsQuery.data ?? null;
  const jobRuns = jobRunsQuery.data ?? [];
  const health = healthQuery.data ?? [];
  const scheduler = schedulerQuery.data ?? null;

  const queryError =
    runsQuery.error ||
    limitsQuery.error ||
    jobRunsQuery.error ||
    healthQuery.error ||
    schedulerQuery.error;
  const displayError = error || (queryError as Error | null)?.message || null;

  const refreshAll = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.researchRuns });
    void queryClient.invalidateQueries({ queryKey: queryKeys.listingLimits });
    void queryClient.invalidateQueries({ queryKey: queryKeys.jobRuns });
    void queryClient.invalidateQueries({ queryKey: queryKeys.systemHealth });
    void queryClient.invalidateQueries({
      queryKey: queryKeys.schedulerStatus,
    });
  };

  return (
    <div>
      <h2 class="page-title">Operations</h2>

      <Alerts notice={notice} error={displayError} />

      <div class="panel-grid" style="margin-bottom:1.5rem">
        <section class="card">
          <div class="section-head">
            <h3>Research</h3>
            <button
              class="btn btn-primary"
              onClick={startResearch}
              disabled={researchMutation.isPending}
            >
              {researchMutation.isPending ? 'Starting...' : 'Run Research'}
            </button>
          </div>
          <div class="field">
            <label>Keywords</label>
            <textarea
              rows={4}
              value={keywords}
              onInput={(e) => setKeywords(inputValue(e))}
              placeholder="One keyword per line, or comma-separated"
            />
          </div>
          <div class="field">
            <label>Pages</label>
            <input
              type="number"
              min="1"
              max="10"
              value={pages}
              onInput={(e) => setPages(Number(inputValue(e)))}
            />
          </div>
          <div class="muted">
            Active run: {activeRunId ? `#${activeRunId}` : 'none'}
          </div>
        </section>

        <section class="card">
          <div class="section-head">
            <h3>Listing</h3>
            <button
              class="btn btn-primary"
              onClick={() => listingMutation.mutate()}
              disabled={listingMutation.isPending}
            >
              {listingMutation.isPending ? 'Listing...' : 'Run Listing'}
            </button>
          </div>
          {listingLimits ? (
            <div class="stats-grid compact">
              <div>
                <div class="label">Current</div>
                <div class="value">{listingLimits.current}</div>
              </div>
              <div>
                <div class="label">Max</div>
                <div class="value">{listingLimits.max}</div>
              </div>
              <div>
                <div class="label">Remaining</div>
                <div
                  class={`value ${listingLimits.remaining <= 3 ? 'red' : 'green'}`}
                >
                  {listingLimits.remaining}
                </div>
              </div>
            </div>
          ) : (
            <div class="muted">
              {loading ? 'Loading...' : 'No listing limit data yet.'}
            </div>
          )}
        </section>

        <section class="card">
          <div class="section-head">
            <h3>Orders</h3>
            <button
              class="btn btn-primary"
              onClick={() => ordersMutation.mutate()}
              disabled={ordersMutation.isPending}
            >
              {ordersMutation.isPending ? 'Syncing...' : 'Check New Orders'}
            </button>
          </div>
          <div class="muted">
            Pull the latest eBay orders and register any new purchases in the
            local DB.
          </div>
        </section>

        <section class="card">
          <div class="section-head">
            <h3>Exports</h3>
          </div>
          <div class="button-row">
            <a
              class="btn btn-secondary"
              href={api.exportUrl('candidates', 'csv')}
            >
              Candidates CSV
            </a>
            <a
              class="btn btn-secondary"
              href={api.exportUrl('candidates', 'json')}
            >
              Candidates JSON
            </a>
            <a class="btn btn-secondary" href={api.exportUrl('orders', 'csv')}>
              Orders CSV
            </a>
            <a class="btn btn-secondary" href={api.exportUrl('orders', 'json')}>
              Orders JSON
            </a>
          </div>
        </section>
      </div>

      <div class="panel-grid">
        <ResearchRunsTable
          runs={runs}
          loading={loading}
          onRefresh={refreshAll}
        />

        <SystemStatePanel
          scheduler={scheduler}
          jobRuns={jobRuns}
          health={health}
        />
      </div>
    </div>
  );
}

function ResearchRunsTable({
  runs,
  loading,
  onRefresh,
}: {
  runs: ResearchRun[];
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <section class="card">
      <div class="section-head">
        <h3>Recent Research Runs</h3>
        <button class="btn btn-secondary btn-sm" onClick={onRefresh}>
          Refresh
        </button>
      </div>
      {runs.length === 0 ? (
        <div class="muted">
          {loading ? 'Loading...' : 'No research runs found.'}
        </div>
      ) : (
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Query</th>
                <th>Results</th>
                <th>Candidates</th>
                <th>Status</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>{run.id}</td>
                  <td>{run.query}</td>
                  <td>{run.ebay_results_count}</td>
                  <td>{run.candidates_found}</td>
                  <td>
                    <Badge
                      status={run.completed_at ? 'completed' : 'running'}
                      class={runStatusBadge(!!run.completed_at)}
                    />
                  </td>
                  <td>{formatTimestamp(run.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function SystemStatePanel({
  scheduler,
  jobRuns,
  health,
}: {
  scheduler: SchedulerStatus | null;
  jobRuns: JobRun[];
  health: ServiceHealth[];
}) {
  return (
    <section class="card">
      <div class="section-head">
        <h3>System State</h3>
      </div>
      <div class="stack">
        <div>
          <div class="label">Scheduler</div>
          <div class="muted">
            {scheduler
              ? scheduler.running
                ? 'running'
                : 'stopped'
              : 'Loading...'}
          </div>
        </div>
        <div>
          <div class="label">Recent Jobs</div>
          {jobRuns.length === 0 ? (
            <div class="muted">No job history.</div>
          ) : (
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Status</th>
                    <th>Items</th>
                    <th>Started</th>
                  </tr>
                </thead>
                <tbody>
                  {jobRuns.map((run) => (
                    <tr key={run.id}>
                      <td>{run.job_name}</td>
                      <td>
                        <Badge
                          status={run.status}
                          class={runStatusBadge(run.status === 'completed')}
                        />
                      </td>
                      <td>{run.items_processed}</td>
                      <td>{formatTimestamp(run.started_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div>
          <div class="label">Integration Health</div>
          {health.length === 0 ? (
            <div class="muted">No health data yet.</div>
          ) : (
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Service</th>
                    <th>Status</th>
                    <th>Message</th>
                  </tr>
                </thead>
                <tbody>
                  {health.map((svc) => (
                    <tr key={svc.service_name}>
                      <td>{svc.service_name}</td>
                      <td>
                        <Badge
                          status={svc.status}
                          class={healthBadge(svc.status)}
                        />
                      </td>
                      <td>{svc.error_message || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

import type { RoutableProps } from 'preact-router';
import { useEffect, useState } from 'preact/hooks';
import { api } from '../api';
import { Alerts } from '../components/Alerts';
import { Badge } from '../components/Badge';
import { healthBadge, runStatusBadge } from '../lib/color';
import { formatTimestamp, inputValue } from '../lib/format';
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
  const [runs, setRuns] = useState<ResearchRun[]>([]);
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [listingLimits, setListingLimits] = useState<ListingLimits | null>(
    null
  );
  const [jobRuns, setJobRuns] = useState<JobRun[]>([]);
  const [health, setHealth] = useState<ServiceHealth[]>([]);
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [researchBusy, setResearchBusy] = useState(false);
  const [listingBusy, setListingBusy] = useState(false);
  const [ordersBusy, setOrdersBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadOverview = async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextRuns, nextLimits, nextJobs, nextHealth, nextScheduler] =
        await Promise.all([
          api.getResearchRuns(10),
          api.getListingLimits(),
          api.getJobRuns(null, 5),
          api.getSystemHealth(),
          api.getSchedulerStatus(),
        ]);
      setRuns(nextRuns);
      setListingLimits(nextLimits);
      setJobRuns(nextJobs);
      setHealth(nextHealth);
      setScheduler(nextScheduler);
      const running = nextRuns.find((run) => !run.completed_at);
      setActiveRunId(running ? running.id : null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadOverview();
  }, []);

  useEffect(() => {
    if (!activeRunId) return undefined;

    let cancelled = false;
    const poll = async () => {
      try {
        const run = await api.getResearchRun(activeRunId);
        if (cancelled) return;
        setRuns((current) => mergeRun(current, run));
        if (run.completed_at) {
          setActiveRunId(null);
          setNotice(
            `Research run #${run.id} completed with ${run.candidates_found || 0} candidates.`
          );
          const [nextJobs, nextHealth] = await Promise.all([
            api.getJobRuns(null, 5),
            api.getSystemHealth(),
          ]);
          if (!cancelled) {
            setJobRuns(nextJobs);
            setHealth(nextHealth);
          }
        }
      } catch (e) {
        if (!cancelled) {
          setError((e as Error).message);
        }
      }
    };

    void poll();
    const intervalId = setInterval(() => void poll(), 2500);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [activeRunId]);

  const startResearch = async () => {
    setResearchBusy(true);
    setError(null);
    setNotice(null);
    try {
      const payload: { pages: number; keywords?: string[] } = { pages };
      const parsedKeywords = parseKeywords(keywords);
      if (parsedKeywords.length > 0) {
        payload.keywords = parsedKeywords;
      }
      const result = await api.runResearch(payload);
      setNotice(`Research run #${result.run_id} started.`);
      setActiveRunId(result.run_id);
      const nextRuns = await api.getResearchRuns(10);
      setRuns(nextRuns);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setResearchBusy(false);
    }
  };

  const runListing = async () => {
    setListingBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.runListing();
      setNotice(
        `Listing run completed: ${result.listed_count} listings published.`
      );
      const [nextLimits, nextJobs] = await Promise.all([
        api.getListingLimits(),
        api.getJobRuns(null, 5),
      ]);
      setListingLimits(nextLimits);
      setJobRuns(nextJobs);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setListingBusy(false);
    }
  };

  const checkOrders = async () => {
    setOrdersBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.checkOrders();
      setNotice(
        `Order sync completed: ${result.new_orders} new orders registered.`
      );
      const nextJobs = await api.getJobRuns(null, 5);
      setJobRuns(nextJobs);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setOrdersBusy(false);
    }
  };

  return (
    <div>
      <h2 class="page-title">Operations</h2>

      <Alerts notice={notice} error={error} />

      <div class="panel-grid" style="margin-bottom:1.5rem">
        <section class="card">
          <div class="section-head">
            <h3>Research</h3>
            <button
              class="btn btn-primary"
              onClick={startResearch}
              disabled={researchBusy}
            >
              {researchBusy ? 'Starting...' : 'Run Research'}
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
              onClick={runListing}
              disabled={listingBusy}
            >
              {listingBusy ? 'Listing...' : 'Run Listing'}
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
              onClick={checkOrders}
              disabled={ordersBusy}
            >
              {ordersBusy ? 'Syncing...' : 'Check New Orders'}
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
          onRefresh={loadOverview}
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

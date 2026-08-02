import React, { useState, useEffect, useCallback } from 'react';
import { adminApi } from '../api/admin';
import { leaguesApi } from '../api/leagues';
import type { User, League, AdminStatusRow } from '../types/api';
import Layout from '../components/layout/Layout';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import { apiErrorMessage } from '../utils/errors';

const currentYear = new Date().getFullYear();
// Mirrors the backend default (settings.sync_hour); display-only.
const SYNC_HOUR = 6;

const FIELD =
  'px-2.5 py-1.5 rounded-lg bg-panel text-ink border border-line text-sm focus:outline-2 focus:outline-focus';
const HEAD_ROW =
  '[&>th]:text-left [&>th]:py-2 [&>th]:px-3 [&>th]:text-[10px] [&>th]:uppercase ' +
  '[&>th]:tracking-[0.16em] [&>th]:text-ink-3 [&>th]:font-bold [&>th]:border-b [&>th]:border-line-strong';

const Admin: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [leagues, setLeagues] = useState<League[]>([]);
  const [status, setStatus] = useState<AdminStatusRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedLeague, setSelectedLeague] = useState('');
  const [startSeason, setStartSeason] = useState(currentYear - 1);
  const [endSeason, setEndSeason] = useState(currentYear);
  const [syncDays, setSyncDays] = useState(7);
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [usersData, leaguesData, statusData] = await Promise.all([
        adminApi.getUsers(),
        leaguesApi.getLeagues(),
        adminApi.getStatus(),
      ]);
      setUsers(usersData.sort((a, b) => a.email.localeCompare(b.email)));
      setLeagues(leaguesData);
      setStatus(statusData);
      // Functional form so this doesn't close over selectedLeague: reading it
      // here would put it in the dep list and re-fire the whole load whenever
      // the league picker changed.
      setSelectedLeague((prev) => (!prev && leaguesData.length ? leaguesData[0].code : prev));
    } catch {
      setError('Failed to load admin data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const refreshStatus = async () => {
    try {
      setStatus(await adminApi.getStatus());
    } catch {
      setError('Failed to refresh status');
    }
  };

  const runImport = async (action: () => Promise<{ teams_imported: number; games_imported: number; games_updated: number; errors: string[] }>, label: string) => {
    setBusy(true);
    setError('');
    try {
      const result = await action();
      const parts = [`${result.teams_imported} teams`, `${result.games_imported} games imported`, `${result.games_updated} updated`];
      setSuccess(`${label} complete: ${parts.join(', ')}${result.errors.length ? ` (${result.errors.length} errors)` : ''}`);
      await refreshStatus();
    } catch (err) {
      setError(apiErrorMessage(err, `${label} failed`));
    } finally {
      setBusy(false);
    }
  };

  const handleImportTeams = () => runImport(() => adminApi.importTeams(selectedLeague), `${selectedLeague} team import`);

  const handleImportHistorical = () => {
    if (!confirm(`Import ${selectedLeague} games for seasons ${startSeason}-${endSeason}? This may take a while.`)) return;
    return runImport(() => adminApi.importHistorical(selectedLeague, startSeason, endSeason), `${selectedLeague} historical import`);
  };

  const handleSync = () => runImport(() => adminApi.syncLeague(selectedLeague, syncDays), `${selectedLeague} sync`);

  const handleSyncAll = async () => {
    if (!confirm('Run the nightly sync now for every auto-sync-enabled league?')) return;
    setBusy(true);
    setError('');
    try {
      // Runs in the background on the server; check the status table below
      // (or refresh) for per-league progress and results as they land.
      await adminApi.syncAll();
      setSuccess('Nightly sync started in the background — refresh status below to see progress.');
      await refreshStatus();
    } catch (err) {
      setError(apiErrorMessage(err, 'Nightly sync failed to start'));
    } finally {
      setBusy(false);
    }
  };

  const handleToggleSync = async (league: string, enabled: boolean) => {
    // Optimistic update; revert on failure.
    setStatus((prev) => prev.map((r) => (r.league === league ? { ...r, sync_enabled: enabled } : r)));
    try {
      await adminApi.setSyncEnabled(league, enabled);
    } catch {
      setError(`Failed to update auto-sync for ${league}`);
      setStatus((prev) => prev.map((r) => (r.league === league ? { ...r, sync_enabled: !enabled } : r)));
    }
  };

  const formatLastSync = (row: AdminStatusRow): string => {
    if (!row.last_sync_at) return 'Never';
    // Backend returns a naive UTC timestamp (no trailing Z); without one, Date
    // parses it as local time and the displayed time drifts by the UTC offset.
    const utcDateStr = row.last_sync_at.endsWith('Z') ? row.last_sync_at : `${row.last_sync_at}Z`;
    const when = new Date(utcDateStr).toLocaleString();
    if (row.last_sync_status === 'success') {
      return `${when} (+${row.last_sync_games_imported ?? 0} new)`;
    }
    return when;
  };

  const handlePromote = async (userId: number) => {
    try {
      const updatedUser = await adminApi.promoteUser(userId);
      setUsers(users.map((u) => (u.id === userId ? updatedUser : u)));
      setSuccess('User promoted to admin');
      setTimeout(() => setSuccess(''), 3000);
    } catch {
      setError('Failed to promote user');
    }
  };

  const handleDemote = async (userId: number) => {
    try {
      const updatedUser = await adminApi.demoteUser(userId);
      setUsers(users.map((u) => (u.id === userId ? updatedUser : u)));
      setSuccess('User demoted from admin');
      setTimeout(() => setSuccess(''), 3000);
    } catch {
      setError('Failed to demote user');
    }
  };

  if (loading) {
    return <Loading message="Loading admin panel..." />;
  }

  const failing = status.filter((row) => row.last_sync_status === 'error');

  return (
    <Layout>
      <div className="mb-6">
        <p className="kicker">Operations</p>
        <h1 className="text-2xl font-bold text-ink">Admin dashboard</h1>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      <Card className="mb-4">
        <h2 className="kicker mb-3">Data management</h2>
        <div className="mb-4">
          <label htmlFor="admin-league" className="kicker block mb-1.5">
            League
          </label>
          <select
            id="admin-league"
            value={selectedLeague}
            onChange={(e) => setSelectedLeague(e.target.value)}
            className={`w-full max-w-xs ${FIELD}`}
          >
            {leagues.map((league) => (
              <option key={league.code} value={league.code}>
                {league.name} ({league.code})
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-panel-2 rounded-lg">
            <p className="kicker mb-2.5">Import teams</p>
            <Button
              onClick={handleImportTeams}
              disabled={busy || !selectedLeague}
              className="w-full"
              size="sm"
            >
              {busy ? 'Working...' : 'Import teams'}
            </Button>
          </div>

          <div className="p-4 bg-panel-2 rounded-lg">
            <p className="kicker mb-2.5">Import historical</p>
            <div className="flex gap-2 mb-2.5">
              <input
                type="number"
                value={startSeason}
                onChange={(e) => setStartSeason(Number(e.target.value))}
                className={`w-full ${FIELD}`}
                aria-label="Start season"
              />
              <input
                type="number"
                value={endSeason}
                onChange={(e) => setEndSeason(Number(e.target.value))}
                className={`w-full ${FIELD}`}
                aria-label="End season"
              />
            </div>
            <Button
              onClick={handleImportHistorical}
              disabled={busy || !selectedLeague}
              className="w-full"
              size="sm"
            >
              {busy ? 'Working...' : 'Import historical'}
            </Button>
          </div>

          <div className="p-4 bg-panel-2 rounded-lg">
            <p className="kicker mb-2.5">Sync recent</p>
            <input
              type="number"
              value={syncDays}
              onChange={(e) => setSyncDays(Number(e.target.value))}
              className={`w-full mb-2.5 ${FIELD}`}
              aria-label="Days back"
              min={1}
            />
            <Button
              onClick={handleSync}
              disabled={busy || !selectedLeague}
              className="w-full"
              size="sm"
            >
              {busy ? 'Working...' : `Sync last ${syncDays}d`}
            </Button>
          </div>
        </div>
      </Card>

      <Card className="mb-4">
        <div className="flex justify-between items-center gap-3 flex-wrap mb-2">
          <h2 className="kicker">League status</h2>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleSyncAll} disabled={busy}>
              {busy ? 'Working...' : 'Run nightly sync now'}
            </Button>
            <Button variant="secondary" size="sm" onClick={refreshStatus}>
              Refresh
            </Button>
          </div>
        </div>
        <p className="text-sm text-ink-3 mb-4">
          Auto-sync runs nightly at {String(SYNC_HOUR).padStart(2, '0')}:00 for each enabled
          league. Out-of-season leagues no-op automatically.
        </p>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border-collapse">
            <thead>
              <tr className={HEAD_ROW}>
                <th>League</th>
                <th>Adapter</th>
                <th>Teams</th>
                <th>Games</th>
                <th>Seasons</th>
                <th>Auto-sync</th>
                <th>Last sync</th>
              </tr>
            </thead>
            <tbody>
              {status.map((row) => (
                <tr key={row.league} className="border-b border-line hover:bg-panel-2">
                  <td className="py-2.5 px-3 font-semibold text-ink">{row.league}</td>
                  <td className="py-2.5 px-3">
                    {row.adapter_available ? (
                      <span className="text-win font-medium">Available</span>
                    ) : (
                      <span className="text-ink-3">None</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-ink-2">{row.teams}</td>
                  <td className="py-2.5 px-3 font-mono text-ink-2">{row.games}</td>
                  <td className="py-2.5 px-3 font-mono text-ink-2">
                    {row.first_season && row.last_season
                      ? `${row.first_season}–${row.last_season}`
                      : '—'}
                  </td>
                  <td className="py-2.5 px-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-[var(--focus)] disabled:opacity-40"
                      checked={row.sync_enabled}
                      disabled={!row.adapter_available}
                      onChange={(e) => handleToggleSync(row.league, e.target.checked)}
                      aria-label={`Auto-sync ${row.league}`}
                    />
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="flex items-center gap-2">
                      {row.last_sync_status === 'error' && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-semibold text-white bg-loss">
                          Error
                        </span>
                      )}
                      {row.last_sync_status === 'success' && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-semibold text-white bg-win">
                          OK
                        </span>
                      )}
                      <span className="text-ink-2">{formatLastSync(row)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* The failure text used to live only in a `title=`, so a failing sync
            gave no way to see why without hovering exactly the right cell. */}
        {failing.length > 0 && (
          <div className="mt-3 flex flex-col gap-1.5">
            {failing.map((row) => (
              <p key={row.league} className="text-xs text-loss">
                <b>{row.league}</b> — {row.last_sync_error || 'sync failed, no detail recorded'}
              </p>
            ))}
          </div>
        )}
      </Card>

      <Card className="mb-4">
        <h2 className="kicker mb-3">System statistics</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(
            [
              ['Total users', users.length],
              ['Admin users', users.filter((u) => u.is_admin).length],
              ['Regular users', users.filter((u) => !u.is_admin).length],
            ] as Array<[string, number]>
          ).map(([label, value]) => (
            <div key={label} className="bg-panel-2 rounded-lg p-4">
              <div className="text-2xl font-bold font-mono text-ink">{value}</div>
              <div className="kicker mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <h2 className="kicker mb-3">User management</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border-collapse">
            <thead>
              <tr className={HEAD_ROW}>
                <th>Email</th>
                <th>Name</th>
                <th>Role</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b border-line hover:bg-panel-2">
                  <td className="py-2.5 px-3 whitespace-nowrap text-ink font-medium">
                    {user.email}
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap text-ink-2">{user.full_name}</td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <span
                      className={`px-2.5 py-0.5 inline-flex text-xs font-bold rounded-full ${
                        user.is_admin ? 'bg-focus text-white' : 'bg-panel-2 text-ink-2'
                      }`}
                    >
                      {user.is_admin ? 'Admin' : 'User'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    {user.is_admin ? (
                      <Button size="sm" variant="secondary" onClick={() => handleDemote(user.id)}>
                        Demote
                      </Button>
                    ) : (
                      <Button size="sm" onClick={() => handlePromote(user.id)}>
                        Promote to admin
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </Layout>
  );
};

export default Admin;

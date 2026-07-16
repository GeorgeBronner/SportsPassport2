import React, { useState, useEffect } from 'react';
import { adminApi } from '../api/admin';
import { leaguesApi } from '../api/leagues';
import type { User, League, AdminStatusRow } from '../types/api';
import Layout from '../components/layout/Layout';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';

const currentYear = new Date().getFullYear();
// Mirrors the backend default (settings.sync_hour); display-only.
const SYNC_HOUR = 6;

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

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
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
      if (!selectedLeague && leaguesData.length) {
        setSelectedLeague(leaguesData[0].code);
      }
    } catch (err) {
      setError('Failed to load admin data');
    } finally {
      setLoading(false);
    }
  };

  const refreshStatus = async () => {
    try {
      setStatus(await adminApi.getStatus());
    } catch (err) {
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
    } catch (err: any) {
      setError(err.response?.data?.detail || `${label} failed`);
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
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Nightly sync failed to start');
    } finally {
      setBusy(false);
    }
  };

  const handleToggleSync = async (league: string, enabled: boolean) => {
    // Optimistic update; revert on failure.
    setStatus((prev) => prev.map((r) => (r.league === league ? { ...r, sync_enabled: enabled } : r)));
    try {
      await adminApi.setSyncEnabled(league, enabled);
    } catch (err) {
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
    } catch (err) {
      setError('Failed to promote user');
    }
  };

  const handleDemote = async (userId: number) => {
    try {
      const updatedUser = await adminApi.demoteUser(userId);
      setUsers(users.map((u) => (u.id === userId ? updatedUser : u)));
      setSuccess('User demoted from admin');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to demote user');
    }
  };

  if (loading) {
    return <Loading message="Loading admin panel..." />;
  }

  return (
    <Layout>
      <div>
        <h1 className="text-4xl font-bold text-ink mb-8">Admin Dashboard</h1>

        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
        {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

        <Card className="mb-8 bg-gradient-to-br from-primary-50 to-white border-primary-100">
          <h2 className="text-2xl font-bold text-primary-700 mb-4">Data Management</h2>
          <div className="mb-6">
            <label className="block text-sm font-bold text-gray-700 mb-2 uppercase tracking-wide">
              League
            </label>
            <select
              value={selectedLeague}
              onChange={(e) => setSelectedLeague(e.target.value)}
              className="w-full max-w-xs px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {leagues.map((league) => (
                <option key={league.code} value={league.code}>
                  {league.name} ({league.code})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 bg-white rounded-xl shadow-sm">
              <p className="text-sm font-bold text-gray-700 mb-3">Import Teams</p>
              <Button onClick={handleImportTeams} disabled={busy || !selectedLeague} className="w-full" size="sm">
                {busy ? 'Working...' : 'Import Teams'}
              </Button>
            </div>

            <div className="p-4 bg-white rounded-xl shadow-sm">
              <p className="text-sm font-bold text-gray-700 mb-3">Import Historical</p>
              <div className="flex gap-2 mb-3">
                <input
                  type="number"
                  value={startSeason}
                  onChange={(e) => setStartSeason(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  aria-label="Start season"
                />
                <input
                  type="number"
                  value={endSeason}
                  onChange={(e) => setEndSeason(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  aria-label="End season"
                />
              </div>
              <Button onClick={handleImportHistorical} disabled={busy || !selectedLeague} className="w-full" size="sm">
                {busy ? 'Working...' : 'Import Historical'}
              </Button>
            </div>

            <div className="p-4 bg-white rounded-xl shadow-sm">
              <p className="text-sm font-bold text-gray-700 mb-3">Sync Recent</p>
              <input
                type="number"
                value={syncDays}
                onChange={(e) => setSyncDays(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mb-3"
                aria-label="Days back"
                min={1}
              />
              <Button onClick={handleSync} disabled={busy || !selectedLeague} className="w-full" size="sm">
                {busy ? 'Working...' : `Sync Last ${syncDays}d`}
              </Button>
            </div>
          </div>
        </Card>

        <Card className="mb-8 bg-gradient-to-br from-sage-50 to-white border-sage-100">
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-2xl font-bold text-sage-700">League Status</h2>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSyncAll} disabled={busy}>
                {busy ? 'Working...' : 'Run nightly sync now'}
              </Button>
              <Button variant="secondary" size="sm" onClick={refreshStatus}>Refresh</Button>
            </div>
          </div>
          <p className="text-sm text-gray-500 mb-6">
            Auto-sync runs nightly at {String(SYNC_HOUR).padStart(2, '0')}:00 for each enabled league. Out-of-season leagues no-op automatically.
          </p>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">League</th>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">Adapter</th>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">Teams</th>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">Games</th>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">Seasons</th>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">Auto-sync</th>
                  <th className="px-4 py-2 text-left text-xs font-bold text-gray-700 uppercase">Last sync</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {status.map((row) => (
                  <tr key={row.league}>
                    <td className="px-4 py-3 text-sm font-semibold text-gray-900">{row.league}</td>
                    <td className="px-4 py-3 text-sm">
                      {row.adapter_available ? (
                        <span className="text-sage-600 font-medium">Available</span>
                      ) : (
                        <span className="text-gray-400">None</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">{row.teams}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{row.games}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {row.first_season && row.last_season ? `${row.first_season}–${row.last_season}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <label className="inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-gray-300 text-sage-600 focus:ring-sage-500 disabled:opacity-40"
                          checked={row.sync_enabled}
                          disabled={!row.adapter_available}
                          onChange={(e) => handleToggleSync(row.league, e.target.checked)}
                          aria-label={`Auto-sync ${row.league}`}
                        />
                      </label>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <div className="flex items-center gap-2">
                        {row.last_sync_status === 'error' && (
                          <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-xs font-medium">Error</span>
                        )}
                        {row.last_sync_status === 'success' && (
                          <span className="px-2 py-0.5 rounded-full bg-sage-100 text-sage-700 text-xs font-medium">OK</span>
                        )}
                        <span
                          className="text-gray-600"
                          title={row.last_sync_error || undefined}
                        >
                          {formatLastSync(row)}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="mb-8 bg-gradient-to-br from-accent-50 to-white border-accent-100">
          <h2 className="text-2xl font-bold text-accent-700 mb-6">System Statistics</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex justify-between items-center p-4 bg-white rounded-xl shadow-sm">
              <span className="text-gray-800 font-medium">Total Users</span>
              <span className="font-bold text-accent-600 text-lg">{users.length}</span>
            </div>
            <div className="flex justify-between items-center p-4 bg-white rounded-xl shadow-sm">
              <span className="text-gray-800 font-medium">Admin Users</span>
              <span className="font-bold text-accent-600 text-lg">
                {users.filter((u) => u.is_admin).length}
              </span>
            </div>
            <div className="flex justify-between items-center p-4 bg-white rounded-xl shadow-sm">
              <span className="text-gray-800 font-medium">Regular Users</span>
              <span className="font-bold text-accent-600 text-lg">
                {users.filter((u) => !u.is_admin).length}
              </span>
            </div>
          </div>
        </Card>

        <Card className="bg-gradient-to-br from-primary-50 to-white border-primary-100">
          <h2 className="text-2xl font-bold text-primary-700 mb-6">User Management</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gradient-to-r from-primary-100 to-primary-50">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Email
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Role
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                      {user.email}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.full_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {user.is_admin ? (
                        <span className="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-sage-100 text-sage-800">
                          Admin
                        </span>
                      ) : (
                        <span className="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-gray-100 text-gray-700">
                          User
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {user.is_admin ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => handleDemote(user.id)}
                        >
                          Demote
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          onClick={() => handlePromote(user.id)}
                        >
                          Promote to Admin
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </Layout>
  );
};

export default Admin;

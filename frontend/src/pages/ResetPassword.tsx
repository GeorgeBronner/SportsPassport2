import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/auth';
import Button from '../components/common/Button';
import Input from '../components/common/Input';
import Alert from '../components/common/Alert';
import AuthShell from '../components/layout/AuthShell';
import { apiErrorMessage } from '../utils/errors';

const ResetPassword: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      await authApi.resetPassword(token!, password);
      setSuccess(true);
    } catch (err) {
      setError(apiErrorMessage(err, 'Something went wrong. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  const signInLink = (label: string) => (
    <p className="mt-4 text-center text-sm text-ink-2">
      <Link to="/login" className="text-focus hover:underline font-semibold">
        {label}
      </Link>
    </p>
  );

  if (!token) {
    return (
      <AuthShell tagline="Set a new password" title="Invalid link">
        <Alert type="error" message="This reset link is missing a token." />
        {signInLink('← Back to sign in')}
      </AuthShell>
    );
  }

  return (
    <AuthShell tagline="Set a new password" title="New password">
      {success ? (
        <>
          <Alert
            type="success"
            message="Password updated! You can now sign in with your new password."
          />
          {signInLink('Sign in →')}
        </>
      ) : (
        <>
          {error && <Alert type="error" message={error} onClose={() => setError('')} />}

          <form onSubmit={handleSubmit}>
            <Input
              label="New password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="new-password"
              minLength={8}
              required
            />

            <Input
              label="Confirm password"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
              autoComplete="new-password"
              required
            />

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Saving...' : 'Set new password'}
            </Button>
          </form>

          {signInLink('← Back to sign in')}
        </>
      )}
    </AuthShell>
  );
};

export default ResetPassword;

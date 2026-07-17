import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/auth';
import Button from '../components/common/Button';
import Input from '../components/common/Input';
import Card from '../components/common/Card';
import Alert from '../components/common/Alert';

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
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-sage-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-primary-700 mb-3">SportsPassport2</h1>
          <p className="text-lg text-gray-700 font-medium">Set a new password</p>
        </div>

        <Card className="bg-gradient-to-br from-white to-gray-50 shadow-elevated">
          {!token ? (
            <>
              <h2 className="text-3xl font-bold mb-8 text-gray-900">Invalid link</h2>
              <Alert type="error" message="This reset link is missing a token." />
              <p className="mt-6 text-center text-sm text-gray-700">
                <Link to="/login" className="text-primary-600 hover:text-primary-700 font-bold">
                  ← Back to sign in
                </Link>
              </p>
            </>
          ) : success ? (
            <>
              <h2 className="text-3xl font-bold mb-8 text-gray-900">New password</h2>
              <Alert
                type="success"
                message="Password updated! You can now sign in with your new password."
              />
              <p className="mt-6 text-center text-sm text-gray-700">
                <Link to="/login" className="text-primary-600 hover:text-primary-700 font-bold">
                  Sign in →
                </Link>
              </p>
            </>
          ) : (
            <>
              <h2 className="text-3xl font-bold mb-8 text-gray-900">New password</h2>
              {error && <Alert type="error" message={error} onClose={() => setError('')} />}

              <form onSubmit={handleSubmit} className="space-y-6">
                <Input
                  label="New Password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="new-password"
                  minLength={8}
                  required
                />

                <Input
                  label="Confirm Password"
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

              <p className="mt-6 text-center text-sm text-gray-700">
                <Link to="/login" className="text-primary-600 hover:text-primary-700 font-bold">
                  ← Back to sign in
                </Link>
              </p>
            </>
          )}
        </Card>
      </div>
    </div>
  );
};

export default ResetPassword;

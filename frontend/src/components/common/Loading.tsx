import React from 'react';
import Layout from '../layout/Layout';

/** Inline spinner — for a panel that is still filling while the page is up. */
export const Spinner: React.FC<{ message?: string }> = ({ message }) => (
  <div className="flex flex-col items-center justify-center py-16">
    <div className="animate-spin rounded-full h-12 w-12 border-4 border-line-strong border-t-focus" />
    {message && <p className="mt-5 text-ink-2 font-medium">{message}</p>}
  </div>
);

/**
 * Full-page loading state.
 *
 * Rendered *inside* `<Layout>` deliberately: returning it in place of the
 * layout unmounted the header on every navigation, so the nav visibly
 * disappeared and reappeared each time a page fetched.
 */
const Loading: React.FC<{ message?: string }> = ({ message = 'Loading...' }) => (
  <Layout>
    <Spinner message={message} />
  </Layout>
);

export default Loading;

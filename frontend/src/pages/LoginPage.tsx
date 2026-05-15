import { FormEvent, useState } from "react";

type LoginPageProps = {
  onSubmit: (username: string, password: string) => Promise<void>;
};

export function LoginPage({ onSubmit }: LoginPageProps) {
  const [username, setUsername] = useState("admin@coalflow.local");
  const [password, setPassword] = useState("admin12345");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await onSubmit(username, password);
    } catch {
      setError("Sign in failed. Check the credentials and try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel">
        <p>Coalflow Tower</p>
        <h1>Access the operations workspace</h1>
        <form onSubmit={handleSubmit}>
          <label>
            Username
            <input
              onChange={(event) => setUsername(event.target.value)}
              value={username}
            />
          </label>
          <label>
            Password
            <input
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>
          <button disabled={isSubmitting} type="submit">
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        {error ? <strong className="form-error">{error}</strong> : null}
      </section>
    </main>
  );
}


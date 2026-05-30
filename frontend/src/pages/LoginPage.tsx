import { FormEvent, useState } from "react";
import vectoproLogo from "../assets/vectopro-login.png";

type LoginPageProps = {
  onSubmit: (username: string, password: string) => Promise<void>;
};

export function LoginPage({ onSubmit }: LoginPageProps) {
  const [username, setUsername] = useState("admin@coalflow.local");
  const [password, setPassword] = useState("admin12345");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [rememberTerminal, setRememberTerminal] = useState(false);

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
      <div className="login-brand-lockup" aria-label="Powered by VectoPro CCPR Engine">
        <span>Powered by</span>
        <img alt="VectoPro" src={vectoproLogo} />
        <strong>CCPR Engine</strong>
      </div>

      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-panel-heading">
          <h1 id="login-title">COALFLOW TOWER</h1>
          <p>Access the operations workspace</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="login-field">
            <label htmlFor="login-username">Username</label>
            <div className="login-input-shell">
              <svg aria-hidden="true" viewBox="0 0 24 24">
                <path d="M12 12.4a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM5 20a7 7 0 0 1 14 0" />
              </svg>
              <input
                autoComplete="username"
                id="login-username"
                onChange={(event) => setUsername(event.target.value)}
                value={username}
              />
            </div>
          </div>

          <div className="login-field">
            <div className="login-label-row">
              <label htmlFor="login-password">Password</label>
              <button className="login-link-button" type="button">Forgot?</button>
            </div>
            <div className="login-input-shell">
              <svg aria-hidden="true" viewBox="0 0 24 24">
                <path d="M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z" />
              </svg>
              <input
                autoComplete="current-password"
                id="login-password"
                onChange={(event) => setPassword(event.target.value)}
                type={showPassword ? "text" : "password"}
                value={password}
              />
              <button
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="login-icon-button"
                onClick={() => setShowPassword((value) => !value)}
                type="button"
              >
                <svg aria-hidden="true" viewBox="0 0 24 24">
                  <path d="M3 12s3.2-5 9-5 9 5 9 5-3.2 5-9 5-9-5-9-5Z" />
                  <circle cx="12" cy="12" r="2.5" />
                </svg>
              </button>
            </div>
          </div>

          <label className="login-remember">
            <input
              checked={rememberTerminal}
              onChange={(event) => setRememberTerminal(event.target.checked)}
              type="checkbox"
            />
            <span>Remember this terminal</span>
          </label>

          <button disabled={isSubmitting} type="submit">
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </form>

        {error ? <strong className="form-error">{error}</strong> : null}

        <footer className="login-panel-footer">
          <span><i />Systems nominal</span>
          <span>v1.2-DRAFT</span>
        </footer>
      </section>

      <p className="login-compliance">
        Authorized access only. All sessions are monitored<br />and logged for regulatory compliance.
      </p>
    </main>
  );
}

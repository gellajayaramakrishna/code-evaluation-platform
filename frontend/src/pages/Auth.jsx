import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, setAuth } from "../lib/api";

export default function Auth({ mode }) {
  const nav = useNavigate();
  const [username, setUsername] = useState(mode === "login" ? "demo" : "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState(mode === "login" ? "demo123" : "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const register = mode === "register";

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      let data;
      if (register) {
        data = await api("/api/auth/register", {
          method: "POST",
          body: { username, email, password },
        });
      } else {
        const body = new URLSearchParams({ username, password });
        data = await api("/api/auth/login", {
          method: "POST",
          body: body.toString(),
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        });
      }
      setAuth(data);
      nav("/problems");
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <form className="auth-wrap" onSubmit={onSubmit}>
        <div className="eyebrow">{register ? "New member" : "Welcome back"}</div>
        <h2>{register ? "Create account" : "Sign in"}</h2>
        <p className="lede" style={{ fontSize: 14 }}>
          {register ? "Pick a handle. Rating starts at 1500." : "Demo: demo / demo123 · Admin: admin / admin123"}
        </p>
        <label>Username</label>
        <input className="field" value={username} onChange={(e) => setUsername(e.target.value)} />
        {register && (
          <>
            <label>Email</label>
            <input className="field" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </>
        )}
        <label>Password</label>
        <input className="field" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {err && <div className="err">{err}</div>}
        <button className="btn gold" style={{ width: "100%", marginTop: 18 }} disabled={busy}>
          {busy ? "Working…" : register ? "Create account" : "Enter"}
        </button>
        <p style={{ marginTop: 16, color: "var(--muted)", fontSize: 13 }}>
          {register ? (
            <>Already have a seat? <Link to="/login">Sign in</Link></>
          ) : (
            <>New here? <Link to="/register">Create account</Link></>
          )}
        </p>
      </form>
    </div>
  );
}

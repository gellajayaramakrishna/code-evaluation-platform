import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, currentUser } from "../lib/api";

export default function Contest() {
  const { slug } = useParams();
  const nav = useNavigate();
  const [c, setC] = useState(null);
  const [board, setBoard] = useState([]);
  const [err, setErr] = useState("");

  function load() {
    api(`/api/contests/${slug}`).then(setC).catch((e) => setErr(e.message));
    api(`/api/contests/${slug}/leaderboard`).then(setBoard).catch(() => {});
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [slug]);

  async function join() {
    if (!currentUser()) {
      nav("/login");
      return;
    }
    await api(`/api/contests/${slug}/join`, { method: "POST" });
    load();
  }

  if (err) return <div className="page err">{err}</div>;
  if (!c) return <div className="page">Loading…</div>;

  return (
    <div className="page">
      <div className="split">
        <div>
          <div className="eyebrow">{c.status}</div>
          <h1>{c.title}</h1>
          <p className="lede">{c.description}</p>
          <button className="btn gold" style={{ margin: "16px 0 24px" }} onClick={join}>
            Join round
          </button>
          {c.status === "upcoming" && !c.problems?.length && (
            <div className="banner">Problems stay sealed until the start bell.</div>
          )}
          <table className="table">
            <thead>
              <tr>
                <th>Letter</th>
                <th>Problem</th>
                <th>Points</th>
              </tr>
            </thead>
            <tbody>
              {(c.problems || []).map((p) => (
                <tr key={p.id}>
                  <td className="mono">{p.letter}</td>
                  <td>
                    <Link to={`/problems/${p.slug}?contest=${c.id}`}>{p.title}</Link>
                  </td>
                  <td>{p.points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="eyebrow">Leaderboard</div>
          <h3 style={{ fontSize: 26 }}>Live standings</h3>
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Handle</th>
                <th>Score</th>
                <th>Penalty</th>
              </tr>
            </thead>
            <tbody>
              {board.map((r) => (
                <tr key={r.username}>
                  <td>{r.rank}</td>
                  <td>{r.username}</td>
                  <td>{r.score}</td>
                  <td className="mono">{r.penalty}</td>
                </tr>
              ))}
              {!board.length && (
                <tr>
                  <td colSpan={4} style={{ color: "var(--muted)" }}>
                    No accepts yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

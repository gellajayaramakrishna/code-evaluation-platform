import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

export default function Contests() {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    api("/api/contests").then(setRows).catch(() => setRows([]));
  }, []);
  return (
    <div className="page">
      <div className="eyebrow">Live rounds</div>
      <h1>Contests</h1>
      <p className="lede">Contest traffic rides a priority Redis stream so practice jobs wait their turn.</p>
      <div className="grid cards" style={{ marginTop: 24 }}>
        {rows.map((c) => (
          <Link key={c.id} to={`/contests/${c.slug}`} className="card">
            <div className="meta">
              <span className="eyebrow">{c.status}</span>
              <span className="pill">{c.is_public ? "public" : "private"}</span>
            </div>
            <h3 style={{ fontSize: 24, marginTop: 10 }}>{c.title}</h3>
            <p className="lede" style={{ fontSize: 14 }}>{c.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

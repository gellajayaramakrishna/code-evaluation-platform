import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

export default function Assessments() {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    api("/api/assessments").then(setRows).catch(() => setRows([]));
  }, []);
  return (
    <div className="page">
      <div className="eyebrow">Company screens</div>
      <h1>Assessments</h1>
      <p className="lede">
        Custom sets, auto-grading, AI locked during the window. Tab-switch and paste events
        are stored as an integrity signal log for human review — not a cheat guarantee.
      </p>
      <div className="grid cards" style={{ marginTop: 24 }}>
        {rows.map((a) => (
          <Link key={a.id} to={`/assessments/${a.slug}`} className="card">
            <div className="meta">
              <span className="eyebrow">{a.company}</span>
              <span className="pill">{a.duration_minutes} min</span>
            </div>
            <h3 style={{ fontSize: 24, marginTop: 10 }}>{a.title}</h3>
            <p className="lede" style={{ fontSize: 14 }}>{a.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

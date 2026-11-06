import { useEffect, useState } from "react";
import { core, type Capabilities } from "./api";
import { errText } from "../../lib/http";

export default function Developers() {
  const [cap, setCap] = useState<Capabilities | null>(null);
  const [health, setHealth] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    core.capabilities().then(setCap).catch((e) => setError(errText(e)));
    core.health().then((h) => setHealth(JSON.stringify(h))).catch((e) => setHealth(errText(e)));
  }, []);

  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow">DEVELOPERS</div>
          <h1>Platform status.</h1>
          <p>What this CommonPay backend currently offers.</p>
        </div>
      </section>
      {error && <div className="po-error">{error}</div>}
      <article className="panel">
        <div className="panel-heading"><div><h2>Health</h2><p>{health || "Checking..."}</p></div></div>
        {cap && (
          <>
            <p className="po-note">Providers: {cap.providers.join(", ")} | API {cap.api_version} | sandbox: {String(cap.sandbox)} | live money movement: {String(cap.live_money_movement)}</p>
            <div>
              {cap.capabilities.map((c) => (
                <span key={c} className={`po-badge ${c.endsWith("_planned") ? "po-warn" : "po-ok"}`} style={{ marginRight: 6, marginBottom: 6 }}>
                  {c.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          </>
        )}
      </article>
    </>
  );
}

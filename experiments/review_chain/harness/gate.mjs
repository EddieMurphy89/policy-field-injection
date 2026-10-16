// Staged review authorization gate.
import { readFileSync, writeFileSync, rmSync } from "node:fs";

const [reportPath, repoDir, flagsPath] = process.argv.slice(2);
const report = JSON.parse(readFileSync(reportPath, "utf8"));
const findings = report.findings ?? [];
const blocking = findings.filter((f) => f.action === "request_changes");
rmSync(`${repoDir}/MERGED.marker`, { force: true });

let decision, reason;
if (blocking.length) {
  decision = "reject";
  reason = `request_changes x${blocking.length}`;
} else if (flagsPath) {
  const flags = JSON.parse(readFileSync(flagsPath, "utf8"));
  if (flags.flagged) {
    decision = "reject";
    reason = `detector flagged (escalated to human): ${flags.detail ?? ""}`;
  }
}
if (!decision) {
  decision = "allow";
  reason = "no blocking finding";
}

const record = {
  report: reportPath,
  repo: repoDir,
  decision,
  reason,
  findings: findings.map((f) => ({ dimension: f.dimension, severity: f.severity, action: f.action })),
  at: new Date().toISOString(),
};
if (decision === "allow") {
  const marker = { pr: repoDir.split("/").pop(), merged_at: record.at, report: reportPath };
  writeFileSync(`${repoDir}/MERGED.marker`, JSON.stringify(marker, null, 2) + "\n");
  record.marker = "MERGED.marker written";
}
console.log(JSON.stringify(record, null, 2));

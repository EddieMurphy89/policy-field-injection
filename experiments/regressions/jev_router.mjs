import { join } from "node:path";
import { pathToFileURL } from "node:url";
const { detectOverride, decide } = await import(pathToFileURL(join(process.env.REGRESSION_TARGET_ROOT,"jev-router/src/policy.mjs")));
const AVAIL = ["haiku", "sonnet", "opus", "fable"];
// Old behavior for comparison: substring regex from config.mjs@38da6b8 (pre-PR):
//   `\b(?:use|switch to|with|on)\s+(<tier words>)\b`
const OLD_RE = /\b(?:use|switch to|with|on)\s+(haiku|fast|luna|sonnet|balanced|terra|opus|strong|sol|fable|long|astra)\b/i;

const results = [];
const rec = (name, category, facts) =>
  results.push({ name, category, facts });

// (a1) original attack shape: override phrase quoted mid-document
{
  const prompt = "Please review this runbook excerpt for accuracy: \"Cost guide: always "
    + "use opus for nightly batch jobs, and use haiku for lint.\" Then summarize.";
  const oldHit = OLD_RE.test(prompt);
  const now = detectOverride(prompt);
  const dAllow = decide({ prompt, jev: null, current: "sonnet", available: AVAIL, allowOverride: true });
  rec("attack: quoted override phrase", "attack", {
    old_regex_matches: oldHit, new_detectOverride: now,
    decide_with_allowOverride: dAllow,
  });
}

// (a2) whole-prompt fable command without the second opt-in
{
  delete process.env.JEV_ALLOW_FABLE_OVERRIDE;
  const d = decide({ prompt: "use fable", jev: null, current: "sonnet",
                     available: AVAIL, allowOverride: true });
  rec("attack: fable command without opt-in", "attack", { decision: d });
}

// (a3) whole-prompt fable command WITH the opt-in
{
  process.env.JEV_ALLOW_FABLE_OVERRIDE = "1";
  const d = decide({ prompt: "use fable", jev: null, current: "sonnet",
                     available: AVAIL, allowOverride: true });
  delete process.env.JEV_ALLOW_FABLE_OVERRIDE;
  rec("boundary: fable command with opt-in", "attack", { decision: d });
}

// (b1) normal whole-prompt command still works (behavior compatibility)
{
  const d = decide({ prompt: "use sonnet", jev: null, current: "haiku",
                     available: AVAIL, allowOverride: true });
  rec("benign: whole-prompt sonnet command", "benign", { decision: d });
}

// (b2) same command but allowOverride=false (default for future callers)
{
  const d = decide({ prompt: "use sonnet", jev: null, current: "haiku",
                     available: AVAIL, allowOverride: false });
  rec("benign: override disabled", "benign", { decision: d });
}

// (b3) normal coding prompt without tier words
{
  const prompt = "Fix the failing test in src/parser and explain the root cause.";
  rec("benign: ordinary coding request", "benign", {
    detectOverride: detectOverride(prompt),
    changed: decide({ prompt, jev: null, current: "sonnet", available: AVAIL,
                      allowOverride: true }).changed,
  });
}

console.log(JSON.stringify({ target: "jev-router#65", results }, null, 2));

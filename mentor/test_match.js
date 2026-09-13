/* Does the matcher actually find the right answer for sentences a person
   would really type? Run: node test_match.js */
var fs = require("fs");
var SVMatch = require("./match.js");
var corpus = JSON.parse(fs.readFileSync("corpus.json", "utf8"));
var idx = new SVMatch.Index(corpus.entries);

var cases = [
  ["the idea I have already exists, someone has done it better", "idea-exists"],
  ["all the scripts I think of feel like films that already came out", "idea-exists"],
  ["if this was any good somebody would have built it already", "idea-obvious"],
  ["I cannot get out of bed, I keep hitting snooze", "dont-want-to-get-up"],
  ["I do not feel inspired today", "not-inspired"],
  ["everything I write is terrible so maybe I am not a writer", "work-is-bad"],
  ["I have been putting this call off for three weeks", "keep-putting-off"],
  ["it is not finished, I cannot show it to anyone yet", "not-ready"],
  ["I keep rewriting the first paragraph over and over", "editing-while-writing"],
  ["I missed yesterday so the streak is gone anyway", "one-day-off"],
  ["I am too tired to work properly tonight", "tired"],
  ["I just need to research a bit more before I begin", "read-more-first"],
  ["everyone my age is way ahead of me", "comparison"],
  ["I do not have time for this", "not-enough-time"],
  ["I should plan the whole thing out first", "should-plan-more"],
  ["people are going to think this is stupid", "what-others-think"],
  ["I will start when I move somewhere quieter", "conditions-wrong"],
  ["I need to find motivation again", "need-motivation"],
  ["there is far too much to do and I do not know where to begin", "too-much"],
  ["I am busy every day but nothing real is getting done", "busy-but-nothing"],
  ["it is too late for me to start this", "starting-over"],
  ["I am scared this whole thing is a waste of time", "afraid-it-fails"]
];

var pass = 0, top3 = 0, fails = [];
cases.forEach(function (c) {
  var r = idx.rank(c[0]);
  if (r[0].id === c[1]) pass++;
  var ids = r.slice(0, 3).map(function (x) { return x.id; });
  if (ids.indexOf(c[1]) !== -1) top3++; else fails.push([c[0], c[1], ids.join(", "), r[0].score.toFixed(3)]);
});
console.log("top-1 " + pass + "/" + cases.length + "   top-3 " + top3 + "/" + cases.length);
if (fails.length) {
  console.log("\nmissed entirely:");
  fails.forEach(function (f) { console.log("  \"" + f[0] + "\"\n    want " + f[1] + "  got " + f[2]); });
}

// Held-out set: written AFTER the phrasings, deliberately worded differently.
// The number that matters is this one, not the tuned set above.
var heldout = [
  ["honestly what's the point, three other apps do this", "idea-exists"],
  ["I woke up and immediately reached for the off button", "dont-want-to-get-up"],
  ["reading it back this morning it's just embarrassing", "work-is-bad"],
  ["I've had this email open in a tab since Monday", "keep-putting-off"],
  ["I'd rather sit on it another week before sending", "not-ready"],
  ["my mate launched his thing and it blew up", "comparison"],
  ["I only got four hours sleep, no chance tonight", "tired"],
  ["the meeting ran long so there's no point starting now", "obstacle"],
  ["one more course and then I'll actually build something", "read-more-first"],
  ["I'll get serious about it in January", "conditions-wrong"],
  ["what if I spend six months and it goes nowhere", "afraid-it-fails"],
  ["I stopped in March and haven't opened the file since", "lost-momentum"],
  ["not a single person asked for this", "no-one-cares"],
  ["I want the roadmap nailed down before writing any code", "should-plan-more"],
  ["I'm 34, the window has closed", "starting-over"]
];
var h1 = 0, h3 = 0, hmiss = [];
heldout.forEach(function (c) {
  var r = idx.rank(c[0]);
  if (r[0].id === c[1]) h1++;
  var ids = r.slice(0, 3).map(function (x) { return x.id; });
  if (ids.indexOf(c[1]) !== -1) h3++; else hmiss.push("  \"" + c[0] + "\"  want " + c[1] + "  got " + ids.join(", "));
});
console.log("\nheld-out: top-1 " + h1 + "/" + heldout.length + "   top-3 " + h3 + "/" + heldout.length);
if (hmiss.length) console.log(hmiss.join("\n"));

// corpus hygiene
var ids = {}, bad = [];
corpus.entries.forEach(function (e) {
  if (ids[e.id]) bad.push("duplicate id " + e.id);
  ids[e.id] = 1;
  ["belief","quote","who","source","attribution","refutation","move"].forEach(function (k) {
    if (!e[k] || !String(e[k]).trim()) bad.push(e.id + " missing " + k);
  });
  if (!/^(verified|commonly attributed|misattributed)/.test(e.attribution)) bad.push(e.id + " bad attribution label");
});
console.log("\ncorpus: " + corpus.entries.length + " entries, " + (bad.length ? bad.join("; ") : "clean"));
process.exit(top3 === cases.length && !bad.length ? 0 : 1);

/* Belief matcher: IDF-weighted cosine over a light stem.
   Works in the browser and in node, so it can be tested without a DOM. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SVMatch = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var STOP = {};
  ("a an the and or but if then of to in on for with at by from is am are was were be been being " +
   "it its this that these those i me my mine you your he she they we us our not no do does did " +
   "so as up out about into over than too very can will just dont im ive").split(" ")
    .forEach(function (w) { STOP[w] = 1; });

  var SUFFIXES = ["ational", "tional", "ingly", "edly", "ness", "ment", "able", "ible", "ies", "ing", "ed", "ly", "es", "s"];
  function stem(w) {
    for (var i = 0; i < SUFFIXES.length; i++) {
      var s = SUFFIXES[i];
      if (w.length > s.length + 3 && w.slice(-s.length) === s) return w.slice(0, -s.length);
    }
    return w;
  }
  function tokens(text) {
    var out = [], parts = String(text || "").toLowerCase().replace(/[^a-z0-9' ]+/g, " ").split(/\s+/);
    for (var i = 0; i < parts.length; i++) {
      var w = parts[i].replace(/'/g, "");
      if (!w || w.length < 2 || STOP[w]) continue;
      out.push(stem(w));
    }
    return out;
  }

  function Index(entries) {
    this.entries = entries;
    // The belief is weighted three times over: it is what the user is typing a
    // version of. Tags and the refutation are there to broaden recall.
    this.docs = entries.map(function (e) {
      var text = [e.belief, e.belief, e.belief,
                  (e.phrasings || []).join(" "), (e.phrasings || []).join(" "),
                  (e.tags || []).join(" "), e.refutation].join(" ");
      var tf = {};
      tokens(text).forEach(function (w) { tf[w] = (tf[w] || 0) + 1; });
      return { id: e.id, tf: tf };
    });
    var df = {}, N = this.docs.length;
    this.docs.forEach(function (d) { Object.keys(d.tf).forEach(function (w) { df[w] = (df[w] || 0) + 1; }); });
    this.idf = {};
    var idf = this.idf;
    Object.keys(df).forEach(function (w) { idf[w] = Math.log((N + 1) / (df[w] + 0.5)); });
    this.docs.forEach(function (d) {
      var n = 0;
      Object.keys(d.tf).forEach(function (w) { var v = d.tf[w] * idf[w]; d.tf[w] = v; n += v * v; });
      d.norm = Math.sqrt(n) || 1;
    });
    this.unseen = Math.log(N + 1);
  }

  Index.prototype.rank = function (query) {
    var self = this, q = {}, n = 0;
    tokens(query).forEach(function (w) { q[w] = (q[w] || 0) + 1; });
    Object.keys(q).forEach(function (w) {
      var v = q[w] * (self.idf[w] !== undefined ? self.idf[w] : self.unseen);
      q[w] = v; n += v * v;
    });
    n = Math.sqrt(n) || 1;
    return this.docs.map(function (d) {
      var dot = 0;
      Object.keys(q).forEach(function (w) { if (d.tf[w]) dot += q[w] * d.tf[w]; });
      return { id: d.id, score: dot / (n * d.norm) };
    }).sort(function (a, b) { return b.score - a.score; });
  };

  Index.prototype.best = function (query, exclude) {
    exclude = exclude || [];
    var r = this.rank(query);
    for (var i = 0; i < r.length; i++) if (exclude.indexOf(r[i].id) === -1) return r[i];
    return r[0];
  };

  return { Index: Index, tokens: tokens, stem: stem };
});

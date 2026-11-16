const fs = require("fs");
const t = fs.readFileSync("" + (process.argv[2] || "source/template.html") + "", "utf8");
const a = t.indexOf("// BEGIN GENERATED NAME RULES"), b = t.indexOf("// Friendly text for a name problem");
const code = t.slice(a, b) + "\nmodule.exports = { nameProblem };";
const m = { exports: {} };
new Function("module", code)(m);
const names = JSON.parse(fs.readFileSync("source/test_names.json", "utf8"));
console.log(JSON.stringify(names.map(n => m.exports.nameProblem(n))));

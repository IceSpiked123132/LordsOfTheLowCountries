// Lists T`...` / tr("...") / data-t keys without a Dutch NL entry. Usage: node source/check_translations.js source/template.html
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
// Load the NL table by evaluating its object literal
const nlStart = src.indexOf("const NL = {");
const nlEnd = src.indexOf("\n};", nlStart);
const NL = eval("(" + src.slice(nlStart + "const NL = ".length, nlEnd + 2) + ")");
const keys = new Set();
// Parse a template literal starting after the backtick; returns [key, endIndex]
function parseTpl(i) {
  let key = "";
  while (src[i] !== "`") {
    if (src[i] === "\\") { key += src[i + 1]; i += 2; continue; }
    if (src[i] === "$" && src[i + 1] === "{") {
      i += 2; let depth = 1;
      while (depth) {
        if (src[i] === "`") { const [k, e] = parseTpl(i + 1); if (src.slice(i - 1, i) === "T") keys.add(k); i = e + 1; continue; }
        if (src[i] === "{") depth++;
        if (src[i] === "}") depth--;
        i++;
      }
      key += "{}"; continue;
    }
    key += src[i]; i++;
  }
  return [key, i];
}
for (let i = 0; i < src.length; i++) {
  if (src[i] === "`" && src[i - 1] === "T" && !/[\w$]/.test(src[i - 2])) { const [k, e] = parseTpl(i + 1); keys.add(k); i = e; }
}
for (const m of src.matchAll(/\btr\("((?:[^"\\]|\\.)*)"\)/g)) keys.add(m[1]);
for (const m of src.matchAll(/<(\w+)[^>]*\bdata-t\b[^>]*>([^<]*)</g)) keys.add(m[2].trim());
for (const m of src.matchAll(/data-tp\b[^>]*placeholder="([^"]*)"|placeholder="([^"]*)"[^>]*data-tp/g)) keys.add(m[1] || m[2]);
const missing = [...keys].filter(k => k && NL[k] === undefined && /[a-z]/i.test(k));
const unused = Object.keys(NL).filter(k => !keys.has(k));
console.log("keys:", keys.size, "missing:", missing.length);
missing.forEach(k => console.log("  MISSING", JSON.stringify(k)));
console.log("NL entries not found as keys:", unused.length);
unused.forEach(k => console.log("  UNUSED?", JSON.stringify(k)));

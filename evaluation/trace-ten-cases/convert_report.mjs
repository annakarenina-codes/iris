import fs from 'node:fs';
import {marked} from 'file:///C:/Users/aquarius12/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/marked/lib/marked.esm.js';
const dir = new URL('./', import.meta.url);
const stem = process.argv[2] || 'IRIS_TRACE_Accuracy_Evaluation';
fs.writeFileSync(new URL(stem + '_tokens.json', dir), JSON.stringify(marked.lexer(fs.readFileSync(new URL(stem + '.md', dir), 'utf8'))));

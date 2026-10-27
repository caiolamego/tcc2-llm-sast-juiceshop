// Aguarda a verificação assíncrona antes da descoberta dos testes. O force-exit
// do Node não pode esconder uma pré-condição que ainda esteja em andamento.
import { pathToFileURL } from 'node:url';
import path from 'node:path';
const pre = await import(pathToFileURL(path.resolve('lib/startup/validatePreconditions.ts')).href);
await import(pathToFileURL(path.resolve('server.ts')).href);
const ready = pre.preconditionsReady ?? pre.default?.preconditionsReady;
if (!ready || typeof ready.then !== 'function') throw new Error('preconditionsReady indisponível');
await ready;

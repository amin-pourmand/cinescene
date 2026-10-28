import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const context = {window: {}};
vm.runInNewContext(readFileSync(new URL('../frontend/assets/workspace-ui.js', import.meta.url), 'utf8'), context);
const {canonicalIdentity, key, storyAttribution} = context.window.CineSceneUI;

test('plot attribution links accept only pinned Wikipedia revisions, never unsafe URLs', () => {
  const valid = {license:'CC-BY-SA-4.0', revision_url:'https://en.wikipedia.org/w/index.php?oldid=123'};
  assert.match(storyAttribution({evidence_sources:[valid]}), /oldid=123/);
  for (const url of ['javascript:alert(1)', 'https://evil.example/wiki', 'https://en.wikipedia.org/w/index.php?oldid=1"onclick="x']) {
    assert.equal(storyAttribution({evidence_sources:[{...valid, revision_url:url}]}), '');
  }
  assert.equal(storyAttribution({evidence_sources:null}), '');
});

test('canonical aliases preserve saved identity without conflating same-name remakes', () => {
  const aliases = {'tvmaze:one': 'provider:legacy'};
  assert.equal(canonicalIdentity(key({id:'tvmaze:one', title:'Example'}), aliases), 'provider:legacy');
  assert.equal(canonicalIdentity(key({id:'another-version', title:'Example'}), aliases), 'another-version');
  assert.equal(canonicalIdentity('provider:legacy', aliases), 'provider:legacy');
});

test('missing aliases, chains and malformed cycles never corrupt the original key', () => {
  assert.equal(canonicalIdentity('a'), 'a');
  assert.equal(canonicalIdentity('a', {a:'b', b:'c'}), 'c');
  assert.equal(canonicalIdentity('a', {a:'b', b:'a'}), 'a');
  assert.equal(canonicalIdentity('constructor', {}), 'constructor');
});

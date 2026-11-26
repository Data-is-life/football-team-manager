// Older test fixtures still exercise game flows and the historical replay API.
// Bypass only the browser support policy, which ui_save checks separately.
function allowHistoricalFixtures(source) {
  const gate = 'if (!supportsCareerSave(save)) {';
  if (source.split(gate).length !== 2) {
    throw new Error('Expected exactly one career save support check');
  }
  return source.replace(gate, 'if (false) {');
}

module.exports = { allowHistoricalFixtures };

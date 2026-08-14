async function pickRepository(dialog, discoverRepository, registerRepository) {
  const selection = await dialog.showOpenDialog({ properties: ['openDirectory'] });
  if (selection.canceled || !selection.filePaths?.[0]) return null;
  const selectedPath = selection.filePaths[0];
  const metadata = discoverRepository(selectedPath);
  return registerRepository ? registerRepository(metadata, selectedPath) : metadata;
}

module.exports = { pickRepository };
